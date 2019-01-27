from typing import Dict, List, Set, Tuple, Optional, Type, overload
from collections.abc import Hashable
from uuid import UUID

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

    def reset(self):
        self._cache = {}

    def _check_object_type(self, obj: Optional[BaseModel]):
        assert obj is not None
        assert isinstance(obj, BaseModel)

    def register(self, obj: BaseModel, force: bool = False) -> bool:
        self._check_object_type(obj)

        obj_type = obj.__class__
        obj_pk = obj.get_keys()
        obj_hash = str(obj._internal_id)

        cached = self.get_by_internal_id(obj_type, obj_hash)

        if not cached and obj_pk:
            cached = self.get(obj_type, obj_pk)

        if cached and force:
            del self._cache[str(obj_type.__name__), str(cached._internal_id)]
            cached = None

        if not cached:
            self._cache[(str(obj_type.__name__), obj_hash)] = obj
            return True

        return False

    def unregister(self, obj: BaseModel):
        self._check_object_type(obj)

        obj_type = obj.__class__
        obj_hash = str(obj._internal_id)

        cached = self.get_by_internal_id(obj.__class__, obj_hash)

        if not cached:
            raise ValueError(f"Object of type `{obj_type.__name__}` and id `{obj_hash}` not found in cache.")

        del self._cache[str(obj_type.__name__), obj_hash]

    def get_type(self, filter_type: Type[BaseModel]) -> Dict[Tuple[str, str], BaseModel]:
        return {
            (model_type, model_hash): model
            for (model_type, model_hash), model in self._cache.items() if filter_type.__name__ == model_type
        }

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

    @overload
    def get_by_internal_id(self, model_type: Type[BaseModel], internal_id: UUID) -> Optional[BaseModel]:
        ...

    @overload
    def get_by_internal_id(self, model_type: Type[BaseModel], internal_id: str) -> Optional[BaseModel]:
        ...

    def get_by_internal_id(self, model_type, internal_id):
        if isinstance(internal_id, UUID):
            internal_id = str(internal_id)

        return self._cache.get((str(model_type.__name__), internal_id), None)

    def get_all_models(self) -> Set[BaseModel]:
        return set(self._cache.values())


class QueryCache:
    """
    Stores query results based on Query hash.
    """

    _cache: Dict[str, List[BaseModel]]

    def __init__(self):
        self._cache = {}

    def reset(self):
        self._cache = {}

    def register(self, obj: BaseQuery, results: List[BaseModel], force: bool = False) -> bool:
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
