import asyncio
from collections import deque
from enum import IntEnum, auto
from functools import wraps
from typing import (Any, Deque, Dict, List, Optional, Set, Tuple, Type, cast,
                    overload)

from .cache import ModelCache, QueryCache
from .dao import BaseDAO
from .graph import (CallbackCoroutineCallable, DependencyGraph,
                    NavigationDirection, Node, NodeProcessException, Tree,
                    TreeProcessException)
from .model import MODEL_UPDATE_EVENT, BaseModel, ValueKey
from .query import BaseQuery
from .state import ModelState, ModelStateMachine, Transition


class TransactionOperationError(Exception):
    """
    Represents a single exception during the `commit` of a Transaction.
    """
    def __init__(self, error: Exception, model: BaseModel):
        super().__init__(error)
        self.model = model


class TransactionError(Exception):
    """
    Represents a collection of exceptions raised during the `commit` of a Transaction.
    """
    def __init__(self, errors: Deque[TransactionOperationError], processed_models: Deque[BaseModel]):
        super().__init__(errors)
        self.errors = errors
        self.models = processed_models


class PersistencyStrategy(IntEnum):
    """
    Defines the strategy of error handling during a Transaction `commit`.

    INTERRUPT_ON_ERROR (default):
        The transaction will be interrupted if any operation with the
        server throws an exception. The operations already performed
        will be persisted on local cache. The commit operation will
        hang until all running tasks finalize, then a TransactionError
        is thrown, containing the list of all models that have not been
        persisted on local cache. This is the recommended approach.

    CONTINUE_ON_ERROR:
        The transaction will continue processing all models in the
        dependency tree that have been marked for modification. The
        framework will persist on local cache only the models that
        have been successfuly synchronized to the remote store. At the
        end, a TransactionError is thrown, containing the list of all
        models that have not been persisted on local cache.
    """
    INTERRUPT_ON_ERROR = auto()
    CONTINUE_ON_ERROR = auto()


class TransactionState(IntEnum):
    """
    Stores the current state of the transaction. The state is used by the transaction
    scope for decision making when particular actions are being executed.

    - STANDBY: The transaction has been created and is not performing any action.
    - GET: The transaction is currently acquiring a model from the remote server.
    - COMMIT: The transaction is performing a commit.
    - ROLLBACK: The transaction is performing a rollback.
    """
    STANDBY = auto()
    GET = auto()
    COMMIT = auto()
    ROLLBACK = auto()


def transactionstate(state: TransactionState):
    """
    Decorates the current method to define the state of the transaction
    during its execution.
    """
    def deco(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            previous = self._state
            self._state = state

            try:
                result = func(self, *args, **kwargs)
                return result
            except Exception:
                raise
            finally:
                self._state = previous

        return wrapper
    return deco


class Transaction:
    """
    Module to manage an abstracted Transaction scope of a REST API server.

    The transaction will manage an internal cache where it stores the models
    retrieved from or persisted to the remote REST API. Models are uniquely
    identified by their internal id and their primary keys. Trying to retrieve
    the same model twice within the same scope will make the transaction return
    the cached models instead of querying the remote server.

    When all models have been modified, created or deleted, the transaction can
    be persisted on the remote server with `commit`.

    The transaction should know how to manipulate each model type by registering
    the respective DAOs with `register_dao`. When asked to `get`, `add` or
    `remove` a model, the Transaction  will look up for the DAO associated with
    the provided model type. If the DAOs raise exeptions during `commit`, then
    the transaction will handle the erros based on the predefined
    PersistenceStrategy provided during instantiation.

    `get` operations will be executed on spot, while `add`, `remove` and `_update`
    will be scheduled to run during `commit`. The transaction will decide in which
    order to manipulate each model based on dependency trees generated in runtime.
    The transaction will try to parallelize the calls to the remote server as much
    as possible to guarantee data consistency. The dependency trees vary with the
    current internal state of each model instance before commit. The state of the
    models is managed by the transaction itself.

    After a `commit` is done, all models that have been persisted on the remote
    server successfully will be persisted on the local cache, even if errors
    occur in parallel tasks. DAOs are allowed to modify the models locally
    during `add` or `update`, since the transaction will pick up the final values
    and persist them on local cache.
    """
    _model_cache: ModelCache
    _query_cache: QueryCache
    _daos: Dict[Type[BaseModel], BaseDAO]
    _strategy: PersistencyStrategy
    _state: TransactionState
    _model_lock: Dict[str, asyncio.Lock]

    def __init__(self, strategy=PersistencyStrategy.INTERRUPT_ON_ERROR):
        self._model_cache = ModelCache()
        self._query_cache = QueryCache()
        self._daos = {}
        self._strategy = strategy
        self._state = TransactionState.STANDBY
        self._model_lock = {}

    def reset(self):
        """
        Resets the internal cache. All references to models are lost.
        """
        self._model_cache.reset()
        self._query_cache.reset()
        self._model_lock = {}

    def register_dao(self, dao: BaseDAO):
        """
        Registers a DAO instance to the transaction and maps its model
        type in the local dictionary.

        :param dao: The DAO instance.
        """
        model_type = dao._model_type

        if model_type not in self._daos:
            self._daos[model_type] = dao

    def get_dao(self, model_type: Type[BaseModel]) -> Optional[BaseDAO]:
        """Returns the DAO associated with the `model_type`.

        :param model_type: The BaseModel subclass.
        :return: The DAO instance, if found. None otherwise.
        """
        return self._daos.get(model_type)

    def _register_model(self, model: BaseModel, force: bool = False, register_children: bool = True):
        self._model_cache.register(model, force)
        self._subscribe_update(model)

        children = model.get_children(recursive=True)
        if register_children:
            for child in children:
                self._model_cache.register(child, force)
                self._subscribe_update(child)
        elif children:
            for child in children:
                if not self._model_cache.get_by_internal_id(child.__class__, child._internal_id):
                    raise RuntimeError(
                        f"Model of id `{child._internal_id}` ({child.__class__.__name__}) "
                        f"is a child of `{model._internal_id}` ({model.__class__.__name__})"
                        " and is not registered in cache."
                    )

    def _subscribe_update(self, model: BaseModel):
        model._listener.subscribe(MODEL_UPDATE_EVENT, self._update)

    def _unsubscribe_update(self, model: BaseModel):
        model._listener.unsubscribe(MODEL_UPDATE_EVENT, self._update)

    def register_model(self, model: BaseModel, force: bool = False, register_children: bool = True):
        """
        Registers the `model` in the internal cache. If the model is already
        registered and `force` is False, then the operation is skipped.

        :param model: The model instance to be registered.
        :param force: Forces the operation if True, skips otherwise.
                      Defaults to False.
        :param register_children: If True, also registers children objects
                                  of the model in the local cache recursively.
                                  Skips children if False. Defaults to True.
        :raises RuntimeError: When `register_children` is False and a child
                              of the model is not registered.
        """
        if not model:
            return

        self._register_model(model, force, register_children)

    async def register_query(
        self, query: BaseQuery, models: List[BaseModel], force: bool = False, register_children: bool = True
    ):
        """
        Registers the `query` and its `models` in the internal cache.
        If any of the models is already registered and `force` is False,
        then they are not persisted into the model cache again.

        :param model: The model instance to be registered.
        :param force: Forces the operation if True, skips otherwise.
                      Defaults to False.
        :param register_children: If True, also registers children objects
                                  of the model in the local cache recursively.
                                  Skips children if False. Defaults to True.
        :raises RuntimeError: When `register_children` is False and a child
                              of the model is not registered.
        """
        registered_models: List[BaseModel] = []

        for model in models:
            self._register_model(model, force, register_children)
            # assuming the previous
            registered_model = await self.get(type(model), model.get_keys())

            if registered_model:
                registered_models.append(registered_model)

        self._query_cache.register(query, registered_models)

    @overload
    async def get(self, model_type: Type[BaseModel], value: Tuple[ValueKey, ...]) -> Optional[BaseModel]:
        ...

    @overload
    async def get(self, model_type: Type[BaseModel], value: List[ValueKey]) -> Optional[BaseModel]:
        ...

    @overload
    async def get(self, model_type: Type[BaseModel], value: ValueKey) -> Optional[BaseModel]:
        ...

    @transactionstate(TransactionState.GET)
    async def get(self, model_type, value):
        """
        Tries retrieving the model of type `model_type` and primary key `value`
        from local cache. If not found, then calls the `get` method of the DAO
        associated to the `model_type`. Returns None if no model is found.

        :param model_type: The BaseModel subclass representing the model.
        :param value: The primary key collection that represents the model.
        :raises RuntimeError: When no DAO is associated with the `model_type`.
        :return: The model instance if found, None otherwise.
        """
        if isinstance(value, list):
            value = tuple(value)

        if not isinstance(value, tuple):
            value = (value,)

        model_lock = self._get_model_lock(model_type, value)

        async with model_lock:
            model: BaseModel = self._model_cache.get_by_primary_key(model_type, value)
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

        return None

    def _get_model_lock(self, model_type: Type[BaseModel], value: Tuple[ValueKey, ...]) -> asyncio.Lock:
        lock_hash = f"{model_type.__name__}/{str(value)}"
        self._model_lock.setdefault(lock_hash, asyncio.Lock())
        return self._model_lock[lock_hash]

    def add(self, model: BaseModel) -> bool:
        """
        Adds new `model` to the local cache and schedules for adding in the remote
        server during `commit`.

        :param model: The model instance.
        :raises RuntimeError: If the model has been already registered in cache.
        :return: True if the model is scheduled for adding, False otherwise.
        """
        assert model is not None

        model_cache = self._model_cache.get_by_internal_id(model.__class__, model._internal_id)
        if model_cache:
            raise RuntimeError(f"Model of id `{model._internal_id}` is already registered in" " internal cache.")

        keys = model.get_keys()
        if keys:
            model_cache = self._model_cache.get_by_primary_key(model.__class__, keys)
            if model_cache:
                raise RuntimeError(f"Model with keys `{keys}` is already registered in" " internal cache.")

        model._state = ModelStateMachine.transition(Transition.ADD_OBJECT, None)
        self._register_model(model, force=False, register_children=False)

        return model._state == ModelState.NEW

    def _assert_cache_internal_id(self, model: BaseModel) -> BaseModel:
        assert model is not None

        model_cache = self._model_cache.get_by_internal_id(model.__class__, model._internal_id)
        if not model_cache:
            raise RuntimeError(f"Model with internal id {model._internal_id} not found on cache.")

        return model_cache

    def remove(self, model: BaseModel) -> bool:
        """
        Schedules model for removal on the remote server during `commit`.

        :param model: The model instance.
        :return: True if model is scheduled for removal, False otherwise.
        """
        model_cache = self._assert_cache_internal_id(model)
        model_cache._state = ModelStateMachine.transition(Transition.REMOVE_OBJECT, model_cache._state)

        return model_cache._state == ModelState.DELETED

    def _update(self, model: BaseModel) -> bool:
        # During COMMIT, ROLLBACK and GET, all changes to models
        # should be permanent, therefore we persist any change
        # and avoid changing the state of the models
        if self._state in (TransactionState.COMMIT, TransactionState.ROLLBACK, TransactionState.GET):
            model._persist()
            return False

        updated = False

        new_state = ModelStateMachine.transition(Transition.UPDATE_OBJECT, model._state)
        if new_state in (ModelState.DIRTY, ModelState.NEW):
            updated = bool(model._persistent_values)
            if not updated and new_state == ModelState.DIRTY:
                new_state = ModelStateMachine.transition(Transition.CLEAN_OBJECT, model._state)
            elif new_state == ModelState.NEW:
                model._persist()

        model._state = new_state
        return updated

    async def query(self, query: BaseQuery, force: bool = False) -> List[BaseModel]:
        """
        Runs custom query `query` and registers results on local cache.

        When new queries are run for the first time, the results are
        persisted into the query and model caches. Models that already
        exist in cache (by checking their primary keys) are not registered
        again (even if `force` = True), to preserve the information
        already stored and avoid discrepancies on the business level.

        The returning values from the query will contain only the models
        that are registered in the cache. Discarded models are replaced
        with their cached version.

        :param query: The query instance to be executed.
        :param force: Forces running the query even if it has been
                      already cached.
        :return: The list of models retrieved by the query.
        """
        if not force:
            cached_results = self._query_cache.get(query)
            if cached_results is not None:
                return cached_results

        results = await query(self)
        await self.register_query(query, results, force=False)

        # Registering the cache above without forcing the values
        # into the model cache might cause double instances of the
        # same model to exist (one from the incoming query, and one
        # previously registered by another query or a get). Therefore,
        # results from the query should updated to return the
        # combination between new results from the current query and
        # old results coming from the cache. As this is already handled
        # by register_query, all we need to do is to retrieve the final
        # values stored for the query in cache
        return self._query_cache.get(query)

    def _get_models_by_state(self, state: Tuple[ModelState, ...], models: Optional[Set[BaseModel]] = None):
        models = self._model_cache.get_all_models() if not models else models
        return set([model for model in models if model._state in state])

    def _get_models_to_add(self, models: Optional[Set[BaseModel]] = None) -> Set[BaseModel]:
        return self._get_models_by_state((ModelState.NEW,), models)

    def _get_models_to_update(self, models: Optional[Set[BaseModel]] = None) -> Set[BaseModel]:
        return self._get_models_by_state((ModelState.DIRTY,), models)

    def _get_models_to_remove(self, models: Optional[Set[BaseModel]] = None) -> Set[BaseModel]:
        return self._get_models_by_state((ModelState.DELETED,), models)

    def _get_processed_models(self, models: Optional[Set[BaseModel]] = None) -> Set[BaseModel]:
        return self._get_models_by_state((ModelState.CLEAN, ModelState.DISCARDED), models)

    def get_transaction_models(self, models: Optional[Set[BaseModel]] = None) -> Set[BaseModel]:
        return self._get_models_by_state((ModelState.NEW, ModelState.DIRTY, ModelState.DELETED), models)

    def _check_deleted_models(self, models: Optional[Set[BaseModel]] = None):
        models = set(self._model_cache._id_cache.values()) if not models else models
        nodes = DependencyGraph._get_connected_nodes(models)
        for node in (n for n in nodes if n.node_object._state == ModelState.DELETED):
            for parent_node in node.get_parents(recursive=True):
                parent_model: BaseModel = parent_node.node_object
                if parent_model._state not in (ModelState.DELETED, ModelState.DISCARDED):
                    raise RuntimeError(
                        "Inconsistent tree. Models that are referred by "
                        "other models cannot be deleted."
                    )

    @transactionstate(TransactionState.COMMIT)
    async def commit(self):
        """
        Persists all models on the remote server. Models that have been successfully
        submited are also persisted on the local cache by the end of the operation.

        :raises RuntimeError: When model doesn't have a DAO associated with its type.
        :raises TransactionError: When the commit fails on DAO level.
        """
        cached_values = self._model_cache.get_all_models()

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

        self._check_deleted_models(models_to_remove)

        # add, update and remove get one graph each, as
        # each level needs to be completely finished in
        # order for the next to proceed
        graphs = list(
            map(
                lambda m: DependencyGraph.generate_from_objects(m), (models_to_add, models_to_update, models_to_remove)
            )
        )

        directions: List[NavigationDirection] = [
            NavigationDirection.LEAVES_TO_ROOTS, NavigationDirection.LEAVES_TO_ROOTS, NavigationDirection.ROOTS_TO_LEAVES
        ]

        try:
            await self._process_all_graphs(graphs, directions)
        except TransactionError:
            raise
        finally:
            # clean up models that were discarded
            discarded_models: Set[BaseModel] = set(filter(lambda m: m._state == ModelState.DISCARDED, all_models))
            for model in discarded_models:
                self._model_cache.unregister(model)
                self._unsubscribe_update(model)
            self.update_cache()

    async def _process_all_graphs(self, graphs: List[DependencyGraph], directions: List[NavigationDirection]):
        all_processed_models: Deque[BaseModel] = deque()
        exception_queue: Deque[TransactionOperationError] = deque()
        for graph, direction in zip(graphs, directions):
            try:
                # processes next level, one at a time
                processed_models = await self._process_all_trees(graph, direction)
            except TransactionError as ex:
                processed_models = ex.models
                exception_queue.extendleft(ex.errors)
                # INTERRUPT_ON_ERROR will only allow trees on the same
                # graph to finalize their on going processes - therefore
                # further levels need to be skipped
                if self._strategy == PersistencyStrategy.INTERRUPT_ON_ERROR:
                    break
                # CONTINUE_ON_ERROR will keep going - this statement is
                # superfluous, but was placed to make the operation explicit
                elif self._strategy == PersistencyStrategy.CONTINUE_ON_ERROR:
                    continue
            finally:
                # keeps record of all processed models, in order
                if processed_models:
                    all_processed_models.extendleft(processed_models)

        # processed models are persisted into cache
        for model in all_processed_models:
            # TODO: add event to detect changes on primary keys and
            # propagate the values back into the model cache for remapping
            model._persist()
            model._state = ModelStateMachine.transition(Transition.PERSIST_OBJECT, model._state)

        # propagates exception if exists
        if exception_queue:
            raise TransactionError(exception_queue, all_processed_models)

    async def _process_all_trees(self, graph: DependencyGraph, direction: NavigationDirection) \
            -> Deque[BaseModel]:
        loop = asyncio.get_running_loop()  # noqa
        tasks = [loop.create_task(self._process_tree(tree, direction)) for tree in graph.trees]
        values: Deque[BaseModel] = deque()
        errors: Deque[TransactionOperationError] = deque()

        for task in asyncio.as_completed(tasks):
            task_value: Optional[Deque[BaseModel]] = None
            error_value: Optional[Deque[TransactionOperationError]] = None
            try:
                # awaits each tree to be processed
                task_value = await task
            except TreeProcessException as ex:
                # the awaiting task that triggered the exception needs
                # to be post-processed so all errors and already processed
                # models are collected
                error_value = deque(
                    [
                        TransactionOperationError(e.error, e.node.node_object) for e in ex.processed_values
                        if isinstance(e, NodeProcessException)
                    ]
                )
                task_value = deque([x for x in ex.processed_values if isinstance(x, BaseModel)])

                # INTERRUPT_ON_ERROR will send a cancellation signal to all trees
                # in graph if one tree triggers an exception - trees will finalize
                # their on going business and return the processed models on the
                # await statement
                if self._strategy == PersistencyStrategy.INTERRUPT_ON_ERROR:
                    for tree in graph.trees:
                        tree.cancel()
            finally:
                if task_value is not None:
                    values.extendleft(task_value)
                if error_value is not None:
                    errors.extendleft(error_value)

        # propagates exception if exists
        if errors:
            raise TransactionError(errors, values)

        return values

    async def _process_tree(self, tree: Tree, direction: NavigationDirection) -> Deque[BaseModel]:
        nodes_callables = self._get_nodes_callables(tree.get_nodes())
        return await tree.process(
            set(nodes_callables.items()), direction, self._strategy == PersistencyStrategy.INTERRUPT_ON_ERROR
        )

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
                        await target(x.node_object)
                        return x, x.node_object
                    except Exception as ex:
                        raise NodeProcessException(ex, x)

                return dao_call

            if model._state == ModelState.NEW:
                model_callable = func(dao.add, node)
            elif model._state == ModelState.DIRTY:
                model_callable = func(dao.update, node)
            elif model._state == ModelState.DELETED:
                model_callable = func(dao.remove, node)

            callables[node] = model_callable

        return callables

    @transactionstate(TransactionState.ROLLBACK)
    def rollback(self):
        """
        Discards all changes to the local cache. New models are discarded and
        local changes to models retrieved from the remote are ignored.
        """
        for model in self._model_cache.get_all_models():
            model._state = ModelStateMachine.transition(Transition.ROLLBACK_OBJECT, model._state)
            if model._state == ModelState.DISCARDED:
                self._model_cache.unregister(model)
                self._unsubscribe_update(model)
            else:
                model._rollback()

    def update_cache(self):
        models = self._get_processed_models()
        for model in models:
            self._model_cache.register(model, force=True)
