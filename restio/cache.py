from collections.abc import Hashable
from typing import Dict, List, Optional, Set, Tuple, Type, overload
from uuid import UUID

from .model import BaseModel, ValueKey, _check_model_type
from .query import BaseQuery

IdCacheKey = Tuple[str, str]
KeyCacheKey = Tuple[str, Tuple[ValueKey, ...]]


class ModelCache:
    """
    Stores BaseModel objects in dictionary with (type, hash)
    indexes.
    """

    _id_cache: Dict[IdCacheKey, BaseModel]
    _key_cache: Dict[KeyCacheKey, BaseModel]

    def __init__(self):
        self.reset()

    def reset(self):
        """
        Resets the internal cache.
        """
        self._id_cache = {}
        self._key_cache = {}

    def register(self, obj: BaseModel, force: bool = False) -> bool:
        """Registers a model into the internal cache.

        :param obj: The model to be registered.
        :param force: Forces the registration of the model again if it
                      is already in cache. Defaults to False
        :return: True if the model has been registered. False otherwise.
        """
        obj_type, obj_pk, obj_hash = self._get_type_key_hash(obj)
        cached, cached_model_id, cached_model_key = self._search_model(obj, deep_search=force)

        # now removes the existing models when forcing the operation
        if cached and force:
            self._remove_from_cache(cached_model_id, cached_model_key)
            cached = None

        # inserts the model if not in cache at this point
        has_empty_pk = self._has_empty_pk(obj_pk)
        if not cached:
            self._id_cache[(str(obj_type.__name__), str(obj_hash))] = obj
            if not has_empty_pk:
                self._key_cache[(str(obj_type.__name__), obj_pk)] = obj
            return True

        return False

    def unregister(self, obj: BaseModel):
        """Unregisters a model from cache.

        :param obj: The model to be unregistered.
        :raises ValueError: When model is not found in cache.
        """
        obj_type, obj_pk, obj_hash = self._get_type_key_hash(obj)
        cached, cached_model_id, cached_model_key = self._search_model(obj, deep_search=True)

        if not cached:
            raise ValueError(f"Object of type `{obj_type.__name__}` and id `{obj_hash}` not found in cache.")

        # now remove the cached models
        self._remove_from_cache(cached_model_id, cached_model_key)

    def _get_type_key_hash(self, obj: BaseModel):
        _check_model_type(obj)

        obj_type = obj.__class__
        obj_pk = obj.get_keys()
        obj_hash = obj._internal_id

        return obj_type, obj_pk, obj_hash

    def _search_model(self, obj: BaseModel, deep_search: bool = True) -> \
            Tuple[Optional[BaseModel], Optional[IdCacheKey], Optional[KeyCacheKey]]:

        obj_type, obj_pk, obj_hash = self._get_type_key_hash(obj)

        cached_model_id: Optional[IdCacheKey] = None
        cached_model_key: Optional[KeyCacheKey] = None
        cached: Optional[BaseModel] = None
        key_cached: Optional[BaseModel] = None

        # first try to find the models by their keys
        cached = self.get_by_internal_id(obj_type, obj_hash)
        if cached:
            cached_model_id = (str(obj_type.__name__), str(obj_hash))

        # also try to find the model by its primary key
        if not self._has_empty_pk(obj_pk):
            key_cached = self.get_by_primary_key(obj_type, obj_pk)
            cached = cached or key_cached

            if key_cached:
                cached_model_key = (str(obj_type.__name__), obj_pk)

        # if not found, then try to find them directly by iterating over the
        # stored models - do the same when found in id cache but not on key cache
        if not cached or (deep_search and not key_cached):
            skip_id = bool(cached) or not deep_search
            cached, search_model_id, cached_model_key = self._search_iterative(obj, skip_id_search=skip_id)
            if not skip_id:
                cached_model_id = search_model_id

        return cached, cached_model_id, cached_model_key

    def _search_iterative(self, obj: BaseModel, skip_id_search: bool = False) -> \
            Tuple[Optional[BaseModel], Optional[IdCacheKey], Optional[KeyCacheKey]]:

        cached_model: Optional[BaseModel] = None
        model_id: Optional[IdCacheKey] = None
        model_key: Optional[KeyCacheKey] = None

        if not skip_id_search:
            for model_id, model in self._id_cache.items():
                if model == obj:
                    cached_model = model
                    break
            else:
                model_id = None

        for model_key, model in self._key_cache.items():
            if model == obj:
                cached_model = model
                break
        else:
            model_key = None

        return cached_model, model_id, model_key

    def _has_empty_pk(self, obj_pk):
        if not obj_pk:
            return True

        for pk in obj_pk:
            if pk is None:
                return True
        return False

    def _remove_from_cache(self, cached_model_id: Optional[IdCacheKey], cached_model_key: Optional[KeyCacheKey]):
        if cached_model_id and cached_model_id in self._id_cache:
            del self._id_cache[cached_model_id]
        if cached_model_key and cached_model_key in self._key_cache:
            del self._key_cache[cached_model_key]

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
        if not isinstance(obj, BaseQuery) or not isinstance(obj, Hashable):
            raise TypeError("The provided `obj` should be a hashable instance of BaseQuery")

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
