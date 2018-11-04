from typing import Type, Tuple, List, Dict, Optional, overload, cast
from copy import deepcopy

from .cache import ModelCache, QueryCache
from .model import BaseModel, ValueKey
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
        if not model:
            dao: BaseDAO = self.get_dao(model_type)
            if not dao:
                raise RuntimeError(f"DAO for model type {model_type.__name__} not found for this transaction.")

            model = cast(model_type, dao.get(value))
            self.register_model(model, force=True)

        return model

    def add(self, model: BaseModel):
        ...

    def remove(self, model: BaseModel):
        ...

    def update(self, model: BaseModel):
        ...

    def query(self, query: BaseQuery, force: bool = False):
        if not force:
            cached_results = self._query_cache.get(query)
            if cached_results is not None:
                return cached_results

        results = query(self)
        self.register_query(query, results, force=True)
        return results
