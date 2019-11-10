from collections.abc import Hashable
from typing import Dict, List, Optional, Set, Tuple, Type, overload
from uuid import UUID

from .model import BaseModel, ValueKey
from .query import BaseQuery


class ModelCache:
    """
    Stores BaseModel objects in dictionary with (type, hash)
    indexes.
    """

    _id_cache: Dict[Tuple[str, str], BaseModel]
    _key_cache: Dict[Tuple[str, Tuple[ValueKey, ...]], BaseModel]

    def __init__(self):
        self.reset()

    def reset(self):
        """
        Resets the internal cache.
        """
        self._id_cache = {}
        self._key_cache = {}

    def _check_object_type(self, obj: Optional[BaseModel]):
        assert obj is not None
        assert isinstance(obj, BaseModel)

    def register(self, obj: BaseModel, force: bool = False) -> bool:
        """Registers a model into the internal cache.

        :param obj: The model to be registered.
        :param force: Forces the registration of the model again if it
                      is already in cache. Defaults to False
        :return: True if the model has been registered. False otherwise.
        """
        self._check_object_type(obj)

        obj_type = obj.__class__
        obj_pk = obj.get_keys()
        obj_hash = str(obj._internal_id)

        cached = self.get_by_internal_id(obj_type, obj_hash)
        if not cached and obj_pk:
            cached = self.get_by_primary_key(obj_type, obj_pk)

        has_empty_pk = self._has_empty_pk(obj_pk)
        if cached and force:
            del self._id_cache[str(obj_type.__name__), str(cached._internal_id)]
            if not has_empty_pk:
                del self._key_cache[str(obj_type.__name__), obj_pk]
            cached = None

        if not cached:
            self._id_cache[(str(obj_type.__name__), obj_hash)] = obj
            if not has_empty_pk:
                self._key_cache[(str(obj_type.__name__), obj_pk)] = obj
            return True

        return False

    def unregister(self, obj: BaseModel):
        """Unregisters a model from cache.

        :param obj: The model to be unregistered.
        :raises ValueError: When model is not found in cache.
        """
        self._check_object_type(obj)

        obj_type = obj.__class__
        obj_pk = obj.get_keys()
        obj_hash = str(obj._internal_id)

        has_empty_pk = self._has_empty_pk(obj_pk)
        cached = self.get_by_internal_id(obj.__class__, obj_hash)

        if not cached:
            raise ValueError(f"Object of type `{obj_type.__name__}` and id `{obj_hash}` not found in cache.")

        del self._id_cache[str(obj_type.__name__), obj_hash]
        if not has_empty_pk:
            del self._key_cache[str(obj_type.__name__), obj_pk]

    def _has_empty_pk(self, obj_pk):
        if not obj_pk:
            return True

        for pk in obj_pk:
            if pk is None:
                return True
        return False

    def get_by_primary_key(self, model_type: Type[BaseModel], value: Tuple[ValueKey, ...]) -> Optional[BaseModel]:
        """Finds model in cache by its primary key.

        :param model_type: The model type to be retrieved.
        :param value: The primary key that identifies the model.
        :return: If found in cache, returns the model instance. Returns None otherwise.
        """
        return self._key_cache.get((str(model_type.__name__), value), None)

    def get_by_internal_id(self, model_type: Type[BaseModel], internal_id: UUID) -> Optional[BaseModel]:
        """Finds model in cache by its internal id.

        :param model_type: The model type to be retrieved.
        :param value: The unique internal id that identifies the model.
        :return: If found in cache, returns the model instance. Returns None otherwise.
        """
        return self._id_cache.get((str(model_type.__name__), str(internal_id)), None)

    def get_all_models(self) -> Set[BaseModel]:
        """Returns a set of all models in cache.

        :return: The set containing all models.
        """
        return set(self._id_cache.values())


class QueryCache:
    """
    Stores query results based on Query hash.
    """

    _cache: Dict[str, List[BaseModel]]

    def __init__(self):
        self.reset()

    def reset(self):
        """
        Resets the internal cache.
        """
        self._cache = {}

    def register(self, obj: BaseQuery, results: List[BaseModel], force: bool = False) -> bool:
        """Registers a query in cache.

        :param obj: The query instance.
        :param results: The list of results from the query.
        :param force: Forces registration of the results from query again
                      if it is already registered in cache. Defaults to False
        :return: True if the results have been registered. False otherwise.
        """
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

    @overload
    def get(self, obj_hash: str) -> Optional[List[BaseModel]]:
        ...

    @overload
    def get(self, obj_hash: BaseQuery) -> Optional[List[BaseModel]]:
        ...

    def get(self, obj_hash):
        """Returns results stored in cache for a particular query.

        :param obj_hash: The query hash.
        :type obj_hash: Union[str, BaseQuery]
        :return: The results from the query if stored in cache.
        """
        if isinstance(obj_hash, BaseQuery):
            obj_hash = obj_hash.__hash__()
        return self._cache.get(str(obj_hash))
