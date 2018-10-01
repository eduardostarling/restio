from typing import Dict, List, Tuple, Optional, Type
from collections.abc import Hashable

from .model import BaseModel, T
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
        obj_pk = obj.get_key()

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

    def get(self, model_type: Type[BaseModel], value: T) -> Optional[BaseModel]:
        models = self.get_type(model_type)
        if value and models:
            for model in models.values():
                if model.get_key() == value:
                    return model

        return None

    def get_by_internal_id(self, model_type: Type[BaseModel], obj_hash: str) -> Optional[BaseModel]:
        return self._cache.get((str(model_type.__name__), obj_hash), None)


class QueryCache:
    """

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

        if not cached:
            self._cache[h] = results
            return True

        return False

    def get(self, obj_hash: str) -> Optional[List[BaseModel]]:
        return self._cache.get(str(obj_hash))
