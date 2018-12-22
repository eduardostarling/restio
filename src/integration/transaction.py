from typing import Type, Tuple, Set, List, Dict, Optional, Any, Deque, overload, cast
from copy import deepcopy
import asyncio

from .cache import ModelCache, QueryCache
from .model import BaseModel, ValueKey
from .state import Transition, ModelState, ModelStateMachine
from .query import BaseQuery
from .dao import BaseDAO
from .graph import DependencyGraph, Tree, Node, NavigationDirection, CallbackCoroutineCallable


class Transaction:
    _model_cache: ModelCache
    _query_cache: QueryCache
    _daos: Dict[Type[BaseModel], BaseDAO]

    def __init__(self):
        self._model_cache = ModelCache()
        self._query_cache = QueryCache()
        self._daos = {}

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

    def commit(self):
        # TODO: test
        cached_values = set(self._model_cache._cache.values())

        models_to_add: Set[Node] = set(
            filter(lambda m: m._state == ModelState.NEW, cached_values))
        models_to_update: Set[Node] = set(
            filter(lambda m: m._state == ModelState.DIRTY, cached_values))
        models_to_remove: Set[Node] = set(
            filter(lambda m: m._state == ModelState.DELETED, cached_values))

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

        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._process_all_graphs(graphs, directions))

        for model in all_models:
            model._persist()
            model._state = ModelStateMachine.transition(Transition.PERSIST_OBJECT, model._state)

        discarded_models: Set[BaseModel] = set(filter(lambda m: m._state == ModelState.DISCARDED, all_models))
        for model in discarded_models:
            self._model_cache.unregister(model)

        # TODO: rollback strategy when things go wrong

    async def _process_all_graphs(self, graphs: List[DependencyGraph], directions: List[NavigationDirection]):
        for graph, direction in zip(graphs, directions):
            await self._process_all_trees(graph, direction)

    async def _process_all_trees(self, graph: DependencyGraph, direction: NavigationDirection):
        loop = asyncio.get_running_loop()  # noqa
        tasks = [loop.create_task(self._process_tree(tree, direction)) for tree in graph.trees]
        values: List[Deque[Node]] = []
        for task in asyncio.as_completed(tasks):
            values.append(await task)

        return values

    async def _process_tree(self, tree: Tree, direction: NavigationDirection) -> Deque[Node]:
        nodes_callables = self._get_nodes_callables(tree.get_nodes())
        return await tree.process(set(nodes_callables.items()), direction)

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
                    return x, await target(x.node_object)
                return dao_call

            if model._state == ModelState.NEW:
                model_callable = func(dao.add, node)
            elif model._state == ModelState.DIRTY:
                model_callable = func(dao.update, node)
            elif model._state == ModelState.DELETED:
                model_callable = func(dao.remove, node)

            callables[node] = model_callable

        return callables
