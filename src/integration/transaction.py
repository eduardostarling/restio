from typing import Type, Tuple, List, Dict, Optional, overload, cast
from copy import deepcopy

from .cache import ModelCache, QueryCache
from .model import BaseModel, ValueKey
from .state import Transition, ModelState, ModelStateMachine
from .query import BaseQuery
from .dao import BaseDAO


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
    def get(self, model_type: Type[BaseModel], value: Tuple[ValueKey, ...]) -> Optional[BaseModel]:
        ...

    @overload
    def get(self, model_type: Type[BaseModel], value: List[ValueKey]) -> Optional[BaseModel]:
        ...

    @overload
    def get(self, model_type: Type[BaseModel], value: ValueKey) -> Optional[BaseModel]:
        ...

    def get(self, model_type, value):
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

        model = cast(model_type, dao.get(value))
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

    def query(self, query: BaseQuery, force: bool = False) -> List[BaseModel]:
        if not force:
            cached_results = self._query_cache.get(query)
            if cached_results is not None:
                return cached_results

        results = query(self)
        self.register_query(query, results, force=True)
        return results
