from typing import Dict, List, Tuple, Optional, Type, overload
from collections.abc import Hashable
from copy import copy

from .model import BaseModel, ValueKey
from .query import BaseQuery


class ModelCache:
    """
    Stores BaseModel objects in dictionary with (type, hash)
    indexes.
    """

    _cache: Dict[Tuple[str, str], BaseModel] = {}

    def __init__(self):
        self._cache = {}

    def register(self, obj: BaseModel, force: bool = False) -> bool:
        assert obj is not None
        assert isinstance(obj, BaseModel)

        obj_type = obj.__class__
        obj_hash = str(obj.__hash__())
        obj_pk = obj.get_keys()

        cached = self.get_by_internal_id(obj_type, obj_hash)

        if not cached and obj_pk:
            cached = self.get(obj_type, obj_pk)

        if cached and force:
            del self._cache[str(obj_type.__name__), str(cached.__hash__())]
            cached = None

        if not cached:
            self._cache[(str(obj_type.__name__), obj_hash)] = obj
            return True

        return False

    def get_type(self, filter_type: Type[BaseModel]) -> Dict[Tuple[str, str], BaseModel]:
        return {(model_type, model_hash): model
                for (model_type, model_hash), model in self._cache.items()
                if filter_type.__name__ == model_type}

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
        models = self.get_type(model_type)
        if isinstance(value, list):
            value = tuple(value)

        if not isinstance(value, tuple):
            value = (value,)

        if value and models:
            for model in models.values():
                if model.get_keys() == value:
                    return model.copy()

        return None

    def get_by_internal_id(self, model_type: Type[BaseModel], obj_hash: str) -> Optional[BaseModel]:
        return self._cache.get((str(model_type.__name__), obj_hash), None)


class QueryCache:
    """
    Stores query results based on Query hash.
    """

    _cache: Dict[str, List[BaseModel]]

    def __init__(self):
        self._cache = {}

    def register(self, obj: BaseQuery, results: List[BaseModel],
                 force: bool = False) -> bool:
        assert obj is not None
        assert isinstance(obj, Hashable)

        h = str(obj.__hash__())
        cached = None

        if not force:
            cached = self.get(h)

        if not cached and results:
            self._cache[h] = results
            return True

        return False

    @overload
    def get(self, obj_hash: str) -> Optional[List[BaseModel]]:
        ...

    @overload
    def get(self, obj_hash: BaseQuery) -> Optional[List[BaseModel]]:
        ...

    def get(self, obj_hash):
        if isinstance(obj_hash, BaseQuery):
            obj_hash = obj_hash.__hash__()
        return self._cache.get(str(obj_hash))
