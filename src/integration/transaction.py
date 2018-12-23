from typing import Type, Tuple, Set, List, Dict, Optional, Any, Deque, overload, cast
from copy import deepcopy
from enum import Enum
from collections import deque
import asyncio

from .cache import ModelCache, QueryCache
from .model import BaseModel, ValueKey
from .state import Transition, ModelState, ModelStateMachine
from .query import BaseQuery
from .dao import BaseDAO
from .graph import DependencyGraph, TreeProcessException, Tree, NodeProcessException, Node, \
    NavigationDirection, CallbackCoroutineCallable


class TransactionOperationError(Exception):
    def __init__(self, error: Exception, model: BaseModel):
        super().__init__(error)
        self.model = model


class TransactionError(Exception):
    def __init__(self, errors: Deque[TransactionOperationError], processed_models: Deque[BaseModel]):
        super().__init__()
        self.errors = errors
        self.models = processed_models


class PersistencyStrategy(Enum):

    """
    INTERRUPT_ON_ERROR (default):
        The transaction will be interrupted if any operation with the
        server throws an exception. The operations already performed
        will be persisted on local cache. The commit operation will
        hang until all running tasks finalize, then a TransactionError
        is thrown, containing the list of all models that have not been
        persisted on local cache. This is the recommended approach.
    """
    INTERRUPT_ON_ERROR = 0

    """
    CONTINUE_ON_ERROR:
        The transaction will continue processing all models in the
        dependency tree that have been marked for modification. The
        framework will persist on local cache only the models that
        have been successfuly synchronized to the remote store. At the
        end, a TransactionError is thrown, containing the list of all
        models that have not been persisted on local cache.
    """
    CONTINUE_ON_ERROR = 1


class Transaction:
    _model_cache: ModelCache
    _query_cache: QueryCache
    _daos: Dict[Type[BaseModel], BaseDAO]
    _strategy: PersistencyStrategy

    def __init__(self, strategy=PersistencyStrategy.INTERRUPT_ON_ERROR):
        self._model_cache = ModelCache()
        self._query_cache = QueryCache()
        self._daos = {}
        self._strategy = strategy

    def reset(self):
        self._model_cache.reset()
        self._query_cache.reset()

    def register_dao(self, dao: BaseDAO):
        model_type = dao._model_type

        if model_type not in self._daos:
            self._daos[model_type] = dao

    def get_dao(self, model_type: Type[BaseModel]) -> Optional[BaseDAO]:
        return self._daos.get(model_type)

    def _register_model(self, model: BaseModel, force: bool = False, register_children: bool = True):
        self._model_cache.register(model, force)

        if register_children:
            children = model.get_children(recursive=True)
            for child in children:
                self._model_cache.register(child, force)

    def register_model(self, model: BaseModel, force: bool = False, register_children: bool = True):
        if not model:
            return

        model = model.copy()
        self._register_model(model, force, register_children)

    def register_query(self, query: BaseQuery, models: List[BaseModel], force: bool = False, register_children: bool = True):
        models = deepcopy(models)
        self._query_cache.register(query, models)

        for model in models:
            self._register_model(model, force, register_children)

    @overload
    async def get(self, model_type: Type[BaseModel], value: Tuple[ValueKey, ...]) -> Optional[BaseModel]:
        ...

    @overload
    async def get(self, model_type: Type[BaseModel], value: List[ValueKey]) -> Optional[BaseModel]:
        ...

    @overload
    async def get(self, model_type: Type[BaseModel], value: ValueKey) -> Optional[BaseModel]:
        ...

    async def get(self, model_type, value):
        if isinstance(value, list):
            value = tuple(value)

        if not isinstance(value, tuple):
            value = (value,)

        model: BaseModel = self._model_cache.get(model_type, value)

        if model:
            return model

        dao: BaseDAO = self.get_dao(model_type)
        if not dao:
            raise RuntimeError(f"DAO for model type {model_type.__name__} not found for this transaction.")

        model = cast(model_type, await dao.get(value))
        if model:
            model._state = ModelStateMachine.transition(Transition.EXISTING_OBJECT, None)
            self.register_model(model, force=True)

        return model

    def add(self, model: BaseModel) -> bool:
        assert model is not None

        model_copy = model.copy()
        model_copy._state = ModelStateMachine.transition(Transition.ADD_OBJECT, None)

        return self._model_cache.register(model_copy)

    def _assert_cache_internal_id(self, model: BaseModel) -> BaseModel:
        assert model is not None

        model_cache = self._model_cache.get_by_internal_id(model.__class__, model._internal_id)
        if not model_cache:
            raise RuntimeError(f"Model with internal id {model._internal_id} not found on cache.")

        return model_cache

    def remove(self, model: BaseModel) -> bool:
        model_cache = self._assert_cache_internal_id(model)
        model_cache._state = ModelStateMachine.transition(Transition.REMOVE_OBJECT, model_cache._state)

        return model_cache._state == ModelState.DELETED

    def update(self, model: BaseModel) -> bool:
        model_cache = self._assert_cache_internal_id(model)
        updated = False

        new_state = ModelStateMachine.transition(Transition.UPDATE_OBJECT, model_cache._state)
        if new_state in (ModelState.DIRTY, ModelState.NEW):
            updated = model_cache._update(model)
            if not updated and new_state == ModelState.DIRTY:
                new_state = ModelStateMachine.transition(Transition.CLEAN_OBJECT, model_cache._state)
            elif new_state == ModelState.NEW:
                model_cache._persist()

        model_cache._state = new_state
        return updated

    async def query(self, query: BaseQuery, force: bool = False) -> List[BaseModel]:
        if not force:
            cached_results = self._query_cache.get(query)
            if cached_results is not None:
                return cached_results

        results = await query(self)
        self.register_query(query, results, force=True)
        return results

    def _get_models_to_add(self, models: Optional[Set[BaseModel]] = None) -> Set[BaseModel]:
        models = set(self._model_cache._cache.values()) if not models else models
        return set(filter(lambda m: m._state == ModelState.NEW, models))

    def _get_models_to_update(self, models: Optional[Set[BaseModel]] = None) -> Set[BaseModel]:
        models = set(self._model_cache._cache.values()) if not models else models
        return set(filter(lambda m: m._state == ModelState.DIRTY, models))

    def _get_models_to_remove(self, models: Optional[Set[BaseModel]] = None) -> Set[BaseModel]:
        models = set(self._model_cache._cache.values()) if not models else models
        return set(filter(lambda m: m._state == ModelState.DELETED, models))

    def get_transaction_models(self, models: Optional[Set[BaseModel]] = None) -> Set[BaseModel]:
        models = set(self._model_cache._cache.values()) if not models else models
        return set(filter(lambda m: m._state not in (ModelState.CLEAN, ModelState.DISCARDED), models))

    def commit(self):
        # TODO: test with CONTINUE_ON_ERROR
        cached_values = set(self._model_cache._cache.values())

        models_to_add = self._get_models_to_add(cached_values)
        models_to_update = self._get_models_to_update(cached_values)
        models_to_remove = self._get_models_to_remove(cached_values)

        all_models: Set[BaseModel] = models_to_add.union(models_to_update) \
                                                  .union(models_to_remove)

        # beginning of TODO: optimize by changing architecture
        # Pre-process to check if all models contain DAO's
        for model in all_models:
            dao = self.get_dao(type(model))
            if dao is None:
                raise RuntimeError(f"Model of type `{type(model)}` does not contain a DAO.")
        # end of TODO

        graphs = list(map(lambda m: DependencyGraph.generate_from_objects(m),
                          (models_to_add, models_to_update, models_to_remove)))

        directions: List[NavigationDirection] = [
            NavigationDirection.LEAFS_TO_ROOTS,
            NavigationDirection.LEAFS_TO_ROOTS,
            NavigationDirection.ROOTS_TO_LEAFS
        ]

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(self._process_all_graphs(graphs, directions))
        except TransactionError:
            raise
        finally:
            discarded_models: Set[BaseModel] = set(filter(lambda m: m._state == ModelState.DISCARDED, all_models))
            for model in discarded_models:
                self._model_cache.unregister(model)

    async def _process_all_graphs(self, graphs: List[DependencyGraph], directions: List[NavigationDirection]):
        all_processed_models: Deque[BaseModel] = deque()
        exception_queue: Deque[Exception] = deque()
        for graph, direction in zip(graphs, directions):
            try:
                processed_models = await self._process_all_trees(graph, direction)
            except TransactionError as ex:
                processed_models = ex.models
                exception_queue.extendleft(ex.errors)
            finally:
                if processed_models:
                    all_processed_models.extendleft(processed_models)

        for model in all_processed_models:
            model._persist()
            model._state = ModelStateMachine.transition(Transition.PERSIST_OBJECT, model._state)

        if exception_queue:
            raise TransactionError(exception_queue, all_processed_models)

    async def _process_all_trees(self, graph: DependencyGraph, direction: NavigationDirection) \
            -> Deque[BaseModel]:
        loop = asyncio.get_running_loop()  # noqa
        tasks = [loop.create_task(self._process_tree(tree, direction)) for tree in graph.trees]
        values: Deque[BaseModel] = deque()
        errors: Deque[Exception] = deque()

        for task in asyncio.as_completed(tasks):
            task_value: Optional[Deque[BaseModel]] = None
            error_value: Optional[Deque[TransactionOperationError]] = None
            try:
                task_value = await task
            except TreeProcessException as ex:
                if self._strategy == PersistencyStrategy.INTERRUPT_ON_ERROR:
                    for task in tasks:
                        if not task.done():
                            task.cancel()

                error_value = deque(map(
                    lambda e: TransactionOperationError(e.error, e.node_object),
                    filter(lambda x: isinstance(x, NodeProcessException), ex.processed_values))
                )
                task_value = deque(filter(lambda x: isinstance(x, BaseModel), ex.processed_values))

            finally:
                if task_value is not None:
                    values.extendleft(task_value)
                if error_value is not None:
                    errors.extendleft(error_value)

        if errors:
            raise TransactionError(errors, values)

        return values

    async def _process_tree(self, tree: Tree, direction: NavigationDirection) -> Deque[BaseModel]:
        nodes_callables = self._get_nodes_callables(tree.get_nodes())
        return await tree.process(set(nodes_callables.items()), direction,
                                  self._strategy == PersistencyStrategy.INTERRUPT_ON_ERROR)

    def _get_nodes_callables(self, nodes: Set[Node]) -> Dict[Node, Optional[CallbackCoroutineCallable]]:
        callables = {}

        for node in nodes:
            model = node.node_object
            dao = self.get_dao(type(model))
            if not dao:
                raise RuntimeError(f"Model of type `{type(model)}` does not contain DAOs.")

            model_callable = None

            def func(target, x) -> CallbackCoroutineCallable:
                async def dao_call() -> Tuple[Node, Any]:
                    try:
                        return x, await target(x.node_object)
                    except Exception as ex:
                        raise NodeProcessException(ex, x.node_object)
                return dao_call

            if model._state == ModelState.NEW:
                model_callable = func(dao.add, node)
            elif model._state == ModelState.DIRTY:
                model_callable = func(dao.update, node)
            elif model._state == ModelState.DELETED:
                model_callable = func(dao.remove, node)

            callables[node] = model_callable

        return callables
