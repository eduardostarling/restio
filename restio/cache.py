from typing import Any, Dict, Optional, Set, Tuple, Type, TypeVar
from uuid import UUID

from restio.model import BaseModel, _check_model_type
from restio.query import BaseQuery

ModelType = TypeVar("ModelType", bound=BaseModel)

IdCacheKey = Tuple[Type[ModelType], UUID]
KeyCacheKey = Tuple[Type[ModelType], Tuple[Any, ...]]


class ModelCache:
    """
    Stores BaseModel objects in dictionary with (type, hash) indexes.
    """

    _id_cache: Dict[IdCacheKey, ModelType]
    _key_cache: Dict[KeyCacheKey, ModelType]

    def __init__(self):
        self.reset()

    def reset(self):
        """
        Resets the internal cache.
        """
        self._id_cache = {}
        self._key_cache = {}

    def register(self, obj: ModelType, force: bool = False) -> bool:
        """
        Registers a model into the internal cache.

        :param obj: The model to be registered.
        :param force: Forces the registration of the model again if it is already in
                      cache. Defaults to False.
        :return: True if the model has been registered. False otherwise.
        """
        obj_type, obj_pk, obj_hash = self._get_type_key_hash(obj)
        cached, cached_model_id, cached_model_key = self._search_model(
            obj, deep_search=force
        )

        # now removes the existing models when forcing the operation
        if cached and force:
            self._remove_from_cache(cached_model_id, cached_model_key)
            cached = None

        # inserts the model if not in cache at this point
        has_empty_pk = self._has_empty_pk(obj_pk)
        if not cached:
            self._id_cache[(obj_type, obj_hash)] = obj
            if not has_empty_pk:
                self._key_cache[(obj_type, obj_pk)] = obj
            return True

        return False

    def unregister(self, obj: ModelType):
        """
        Unregisters a model from cache.

        :param obj: The model to be unregistered.
        :raises ValueError: When model is not found in cache.
        """
        obj_type, _, obj_hash = self._get_type_key_hash(obj)
        cached, cached_model_id, cached_model_key = self._search_model(
            obj, deep_search=True
        )

        if not cached:
            raise ValueError(
                f"Object of type `{obj_type.__name__}` and id `{obj_hash}` not found"
                " in cache."
            )

        # now remove the cached models
        self._remove_from_cache(cached_model_id, cached_model_key)

    def has_model(self, model: ModelType) -> bool:
        """
        Indicates if model exists in cache.

        :param model: The model instance.
        :return: True if model exists in cache, False otherwise.
        """
        model_type, keys, obj_hash = self._get_type_key_hash(model)
        return (model_type, keys) in self._key_cache or obj_hash in self._id_cache

    def get_by_primary_key(
        self, model_type: Type[ModelType], keys: Tuple[Any, ...]
    ) -> Optional[ModelType]:
        """
        Finds model in cache by its primary key.

        :param model_type: The model type to be retrieved.
        :param keys: The tuple of primary key that identify the model.
        :return: If found in cache, returns the model instance. Returns None otherwise.
        """
        return self._key_cache.get((model_type, keys), None)

    def get_by_internal_id(
        self, model_type: Type[ModelType], internal_id: UUID
    ) -> Optional[ModelType]:
        """
        Finds model in cache by its internal id.

        :param model_type: The model type to be retrieved.
        :param internal_id: The unique internal id that identifies the model.
        :return: If found in cache, returns the model instance. Returns None otherwise.
        """
        return self._id_cache.get((model_type, internal_id), None)

    def get_all_models(self) -> Set[ModelType]:
        """
        Returns a set of all models in cache.

        :return: The set containing all models.
        """
        return set(self._id_cache.values())

    def _search_model(
        self, obj: ModelType, deep_search: bool = True
    ) -> Tuple[Optional[ModelType], Optional[IdCacheKey], Optional[KeyCacheKey]]:

        obj_type, obj_pk, obj_hash = self._get_type_key_hash(obj)

        cached_model_id: Optional[IdCacheKey] = None
        cached_model_key: Optional[KeyCacheKey] = None
        cached: Optional[ModelType] = None
        key_cached: Optional[ModelType] = None

        # first try to find the models by their keys
        cached = self.get_by_internal_id(obj_type, obj_hash)
        if cached:
            cached_model_id = (obj_type, obj_hash)

        # also try to find the model by its primary key
        if not self._has_empty_pk(obj_pk):
            key_cached = self.get_by_primary_key(obj_type, obj_pk)
            cached = cached or key_cached

            if key_cached:
                cached_model_key = (obj_type, obj_pk)

        # if not found, then try to find them directly by iterating over the
        # stored models - do the same when found in id cache but not on key cache
        if not cached or (deep_search and not key_cached):
            skip_id = bool(cached) or not deep_search
            cached, search_model_id, cached_model_key = self._search_iterative(
                obj, skip_id_search=skip_id
            )
            if not skip_id:
                cached_model_id = search_model_id

        return cached, cached_model_id, cached_model_key

    def _search_iterative(
        self, obj: ModelType, skip_id_search: bool = False
    ) -> Tuple[Optional[ModelType], Optional[IdCacheKey], Optional[KeyCacheKey]]:

        cached_model: Optional[ModelType] = None
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

    def _get_type_key_hash(
        self, obj: ModelType
    ) -> Tuple[Type[ModelType], Tuple[Any, ...], UUID]:
        _check_model_type(obj)

        obj_type = obj.__class__
        obj_pk = tuple(obj.primary_keys.values())
        obj_hash = obj._internal_id

        return obj_type, obj_pk, obj_hash

    def _has_empty_pk(self, obj_pk: Tuple[Any, ...]):
        return not obj_pk or None in obj_pk

    def _remove_from_cache(
        self,
        cached_model_id: Optional[IdCacheKey],
        cached_model_key: Optional[KeyCacheKey],
    ):
        if cached_model_id and cached_model_id in self._id_cache:
            del self._id_cache[cached_model_id]
        if cached_model_key and cached_model_key in self._key_cache:
            del self._key_cache[cached_model_key]


class QueryCache:
    """
    Stores query results based on Query hash.
    """

    _cache: Dict[int, Tuple[ModelType, ...]]

    def __init__(self):
        self.reset()

    def reset(self):
        """
        Resets the internal cache.
        """
        self._cache = {}

    def register(
        self,
        query: BaseQuery[ModelType],
        results: Tuple[ModelType, ...],
        force: bool = False,
    ) -> bool:
        """
        Registers a query in cache.

        :param query: The query instance.
        :param results: The results from the query.
        :param force: Forces registration of the results from query again if it is
                      already registered in cache. Defaults to False
        :return: True if the results have been registered. False otherwise.
        """
        cached = self.get(query) if not force else None

        if not cached:
            self._cache[hash(query)] = results

        return not cached

    def get(self, query: BaseQuery[ModelType]) -> Optional[Tuple[ModelType, ...]]:
        """
        Returns results stored in cache for a particular query.

        :param query: The query instance.
        :return: The results from the query if stored in cache.
        """
        return self._cache.get(hash(query))
