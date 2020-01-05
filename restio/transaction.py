from __future__ import annotations

import asyncio
from enum import IntEnum, auto
from functools import wraps
from typing import (AsyncGenerator, AsyncIterator, Dict, List, Optional, Set,
                    Tuple, Type, cast, overload)

from .cache import ModelCache, QueryCache
from .dao import (BaseDAO, DAOTask, DAOTaskCallable,
                  check_dao_implemented_method)
from .graph import DependencyGraph, NavigationDirection, Node, Tree
from .model import MODEL_UPDATE_EVENT, BaseModel, ValueKey, _check_model_type
from .query import BaseQuery
from .state import ModelState, ModelStateMachine, Transition


class PersistencyStrategy(IntEnum):
    """
    Defines the strategy of error handling during a Transaction `commit`.

    INTERRUPT_ON_ERROR (default):
        The transaction will be interrupted if any operation made by
        a DAO throws an exception. The operations already performed
        will be persisted on local cache, and the on-going tasks in
        the other dependency trees will be finalized. The commit
        operation will hang until all running tasks finalize, then a
        list of all DAOTask's will be returned by the `commit`. This
        is the recommended approach.

    CONTINUE_ON_ERROR:
        The transaction will continue processing all models in the
        dependency tree that have been marked for modification. The
        framework will persist on local cache only the models that
        have been successfuly synchronized to the remote store. No
        cancellation will be done.
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

    def get_dao(self, model_type: Type[BaseModel]) -> BaseDAO:
        """Returns the DAO associated with the `model_type`.

        :param model_type: The BaseModel subclass.
        :raises RuntimeError: If no DAO has been associated to the provided
                              `model_type`.
        :return: The DAO instance, if found.
        """
        dao = self._daos.get(model_type)
        if dao is None:
            raise NotImplementedError(f"Model type `{model_type.__name__}` does not contain a DAO registered.")

        return dao

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
        _check_model_type(model)

        dao = self.get_dao(type(model))
        check_dao_implemented_method(dao.add)

        model_cache = self._model_cache.get_by_internal_id(model.__class__, model._internal_id)
        if model_cache:
            raise RuntimeError(f"Model of id `{model._internal_id}` is already registered in internal cache.")

        keys = model.get_keys()
        if keys:
            model_cache = self._model_cache.get_by_primary_key(model.__class__, keys)
            if model_cache:
                raise RuntimeError(f"Model with keys `{keys}` is already registered in internal cache.")

        model._state = ModelStateMachine.transition(Transition.ADD_OBJECT, None)
        self._register_model(model, force=False, register_children=False)

        return model._state == ModelState.NEW

    def _assert_cache_internal_id(self, model: BaseModel) -> BaseModel:
        _check_model_type(model)

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
        dao = self.get_dao(type(model))
        check_dao_implemented_method(dao.remove)

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

        if new_state == ModelState.DIRTY:
            dao = self.get_dao(type(model))
            check_dao_implemented_method(dao.update)

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
        return self._query_cache.get(query)  # type: ignore

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
    async def commit(self) -> List[DAOTask]:
        """
        Persists all models on the remote server. Models that have been successfully
        submited are also persisted on the local cache by the end of the operation.

        :raises RuntimeError: When model doesn't have a DAO associated with its type.
        :return: A list containing all DAOTask's performed by the commit, in the order
                 in which the operations have been finalized.
        """
        cached_values = self._model_cache.get_all_models()

        models_to_add = self._get_models_to_add(cached_values)
        models_to_update = self._get_models_to_update(cached_values)
        models_to_remove = self._get_models_to_remove(cached_values)

        all_models: Set[BaseModel] = models_to_add.union(models_to_update) \
                                                  .union(models_to_remove)

        self._check_deleted_models(models_to_remove)

        # add, update and remove get one graph each, as
        # each level needs to be completely finished in
        # order for the next to proceed
        graphs = [
            DependencyGraph.generate_from_objects(m)
            for m in (models_to_add, models_to_update, models_to_remove)
        ]

        directions: List[NavigationDirection] = [
            NavigationDirection.LEAVES_TO_ROOTS,
            NavigationDirection.LEAVES_TO_ROOTS,
            NavigationDirection.ROOTS_TO_LEAVES
        ]

        results: List[DAOTask] = []
        try:
            async for task in self._process_all_graphs(graphs, directions):
                results.append(task)
        finally:
            # clean up models that were discarded
            discarded_models: Set[BaseModel] = set(m for m in all_models if m._state == ModelState.DISCARDED)
            for model in discarded_models:
                self._model_cache.unregister(model)
                self._unsubscribe_update(model)
            self.update_cache()
        return results

    async def _process_all_graphs(self, graphs: List[DependencyGraph], directions: List[NavigationDirection]):
        cancel = False

        for graph, direction in zip(graphs, directions):
            # this will avoid moving to the next graph if an error
            # occurs and the cancellation is enabled
            if cancel:
                break

            # processes next level, one at a time
            async for dao_task in self._process_all_trees(graph, direction):
                model = None
                try:
                    # we await here to check if any exceptions were raised
                    # and also to collect the node that was processed
                    await dao_task
                    model = dao_task.model
                except Exception:
                    # INTERRUPT_ON_ERROR will only allow trees on the same
                    # graph to finalize their on going processes - therefore
                    # further levels need to be skipped
                    if self._strategy == PersistencyStrategy.INTERRUPT_ON_ERROR:
                        cancel = True
                    # CONTINUE_ON_ERROR will keep going - this statement is
                    # superfluous, but was placed to make the operation explicit
                    elif self._strategy == PersistencyStrategy.CONTINUE_ON_ERROR:
                        continue
                finally:
                    if model:
                        model._persist()
                        model._state = ModelStateMachine.transition(Transition.PERSIST_OBJECT, model._state)
                    yield dao_task

    async def _process_all_trees(self, graph: DependencyGraph, direction: NavigationDirection) \
            -> AsyncIterator[DAOTask]:

        all_results: List[DAOTask] = []

        # this will iterate over each tree separately
        async def iterate_tree(tree, direction):
            tree_results = []
            async for dao_task in self._process_tree(tree, direction):
                tree_results.append(dao_task)
            return tree_results

        # the following block will guarantee that the trees are triggered in parallel
        # and operations run as fast as possible
        tree_iterate_tasks = [asyncio.create_task(iterate_tree(t, direction)) for t in graph.trees]
        for iterate_task in asyncio.as_completed(tree_iterate_tasks):
            all_results.extend(await iterate_task)

        # with the parallelization, we lost control of the order in which the models were
        # processe between the trees, so we need to reorder and yield back
        for x in sorted(all_results):
            yield x

    async def _process_tree(self, tree: Tree, direction: NavigationDirection) -> AsyncGenerator[DAOTask, None]:
        navigate_queue: asyncio.Queue[Node] = asyncio.Queue()
        finished_queue: asyncio.Queue[DAOTask] = asyncio.Queue()
        tasks: List[asyncio.Task[DAOTask]] = []
        cancel = False

        # collects nodes to be processed
        nodes = tree.get_nodes()
        nodes_callables: Dict[Node, DAOTask] = self._get_dao_tasks(nodes)

        # creates a task to handle the node and propagate
        # the values across the queues
        async def node_task(node):
            nonlocal cancel
            dao_task: DAOTask = nodes_callables[node]

            # we don't care about the value of the task here, we only
            # try and except to catch errors and interrupt the execution
            # if necessary
            try:
                await dao_task
            except Exception:
                # in this case, we flag to interrupt scheduling new tasks
                if self._strategy == PersistencyStrategy.INTERRUPT_ON_ERROR:
                    cancel = True

            # informs tree.navigate that a new node has been processed
            await navigate_queue.put(node)
            # queues up a new value to be yielded
            await finished_queue.put(dao_task)

        async for node in tree.navigate(nodes, direction, navigate_queue):
            # yields the processed values before scheduling
            # a new task
            while not finished_queue.empty():
                yield await finished_queue.get()

            # stops scheduling new values if the task is canceled
            if cancel:
                break

            # schedules a new DAO task
            task = asyncio.create_task(node_task(node))
            tasks.append(task)

        # processes the remaining items after the generator has been
        # finalized
        while not finished_queue.empty():
            yield await finished_queue.get()

    def _get_dao_tasks(self, nodes: Set[Node]) -> Dict[Node, DAOTask]:
        callables = {}

        for node in nodes:
            model = node.node_object
            dao = self.get_dao(type(model))

            model_callable: DAOTaskCallable

            if model._state == ModelState.NEW:
                model_callable = dao.add
            elif model._state == ModelState.DIRTY:
                model_callable = dao.update
            elif model._state == ModelState.DELETED:
                model_callable = dao.remove

            callables[node] = DAOTask(node, model_callable)

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
