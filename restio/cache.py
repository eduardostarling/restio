from typing import Any, Dict, Optional, Set, Tuple, Type, TypeVar

from restio.model import BaseModel, _check_model_type
from restio.query import BaseQuery

ModelType = TypeVar("ModelType", bound=BaseModel)

KeyCacheKey = Tuple[Type[ModelType], Tuple[Any, ...]]


class ModelCache:
    """
    Stores BaseModel objects in dictionary with (type, hash) indexes.
    """

    _id_cache: Set[ModelType]
    _key_cache: Dict[KeyCacheKey, ModelType]

    def __init__(self):
        self.reset()

    def reset(self):
        """
        Resets the internal cache.
        """
        self._id_cache = set()
        self._key_cache = {}

    def register(self, obj: ModelType, force: bool = False) -> bool:
        """
        Registers a model into the internal cache.

        :param obj: The model to be registered.
        :param force: Forces the registration of the model again if it is already in
                      cache. Defaults to False.
        :return: True if the model has been registered. False otherwise.
        """
        in_id_cache: bool = self.is_registered_by_id(obj)
        model_key: Optional[KeyCacheKey]

        if force:
            model_key = self._search_key_for_model(obj, deep_search=True)
            self._remove_from_cache(obj, model_key)
            in_id_cache = False

        model_key = self._get_type_key_hash(obj)

        # inserts the model if not in cache at this point
        if not in_id_cache and (model_key not in self._key_cache or force):
            self._id_cache.add(obj)
            if not self._has_empty_pk(model_key):
                self._key_cache[model_key] = obj
            return True

        return False

    def unregister(self, obj: ModelType):
        """
        Unregisters a model from cache.

        :param obj: The model to be unregistered.
        :raises ValueError: When model is not found in cache.
        """

        if not self.is_registered_by_id(obj):
            raise ValueError(
                f"Provided model `{obj._internal_id}` is not registered to the cache."
            )

        cached_model_key = self._search_key_for_model(obj, deep_search=True)

        # now remove the cached models
        self._remove_from_cache(obj, cached_model_key)

    def has_model(self, model: ModelType) -> bool:
        """
        Indicates if model exists in cache.

        :param model: The model instance.
        :return: True if model exists in cache, False otherwise.
        """
        return self.is_registered_by_id(model)

    def has_model_with_keys(self, model: ModelType):
        """
        Indicates if a model is registered under the keys of the provided `model`.

        :param model: The model instance.
        :return: True if any model with the keys of `model` is found in the model
                 cache, False otherwise.
        """
        key_hash = self._get_type_key_hash(model)
        return self.has_keys(key_hash)

    def has_keys(self, key_hash: KeyCacheKey) -> bool:
        return not self._has_empty_pk(key_hash) and key_hash in self._key_cache

    def get_by_primary_key(self, key_hash: KeyCacheKey) -> Optional[ModelType]:
        """
        Finds model in cache by its primary key.

        :param model_type: The model type to be retrieved.
        :param keys: The tuple of primary key that identify the model.
        :return: If found in cache, returns the model instance. Returns None otherwise.
        """
        return self._key_cache.get(key_hash, None)

    def is_registered_by_id(self, obj: ModelType) -> bool:
        """
        Indicates if the model `obj` is registered in the Id cache.

        :param obj: The model.
        :return: True if `obj` is in the Id cache, False otherwise.
        """
        return obj in self._id_cache

    def get_all_models(self) -> Set[ModelType]:
        """
        Returns a set of all models in cache.

        :return: The set containing all models.
        """
        return set(self._id_cache.copy())

    def _search_key_for_model(
        self, obj: ModelType, deep_search: bool = True
    ) -> Optional[KeyCacheKey]:

        key_hash = self._get_type_key_hash(obj)
        has_empty_pk = self._has_empty_pk(key_hash)

        # optimize by accessing the cache directly and checking if the model registered
        # with the given key is the actual object we are looking for
        if not has_empty_pk and self.get_by_primary_key(key_hash) == obj:
            return key_hash

        # if not found, then try to find them directly by iterating over the stored
        # models
        return self._search_iterative(obj) if deep_search else None

    def _search_iterative(self, obj: ModelType) -> Optional[KeyCacheKey]:
        model_key: Optional[KeyCacheKey] = None

        for model_key, model in self._key_cache.items():
            if model == obj:
                return model_key

        return None

    def _get_type_key_hash(self, obj: ModelType) -> KeyCacheKey:
        _check_model_type(obj)

        obj_type = obj.__class__
        obj_pk = tuple(obj.primary_keys.values())

        return obj_type, obj_pk

    def _has_empty_pk(self, obj_pk: Optional[KeyCacheKey]):
        return not obj_pk or None in obj_pk[1]

    def _remove_from_cache(
        self, obj: ModelType, cached_model_key: Optional[KeyCacheKey],
    ):
        self._id_cache.discard(obj)
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
