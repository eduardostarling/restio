from typing import Dict, List, Tuple, Optional
from collections.abc import Hashable

from .model import BaseModel
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

        t = obj.__class__
        h = str(obj.__hash__())

        cached = None

        if not force:
            cached = self.get(t, h)

        if not cached:
            self._cache[(str(t.__name__), h)] = obj
            return True

        return False

    def get(self, model_type: type, obj_hash: str) -> Optional[BaseModel]:
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
