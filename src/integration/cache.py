from typing import Dict, List, Optional
from abc import ABC
from collections.abc import Hashable

from .model import BaseModel
from .query import BaseQuery


class BaseCache(ABC):
    _cache: Dict

    def __init__(self):
        self._cache = {}


class ModelCache(BaseCache):
    _cache: Dict[str, Dict[str, BaseModel]] = {}

    def register(self, obj: BaseModel, force: bool = False) -> bool:
        assert obj is not None
        assert isinstance(obj, Hashable)

        t = str(obj.__class__.__name__)
        h = str(obj.__hash__())

        if t not in self._cache:
            self._cache[t] = {}

        cached = None

        if not force:
            cached = self.get(obj.__class__, h)

        if not cached:
            self._cache[t][h] = obj
            return True

        return False

    def get(self, model_type: type, obj_hash: str) -> Optional[BaseModel]:
        model_dict = self._cache.get(str(model_type.__name__), None)
        if model_dict:
            return model_dict.get(str(obj_hash), None)

        return None


class QueryCache(BaseCache):
    _cache: Dict[str, List[BaseModel]]

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
