from .cache import ModelCache, QueryCache
from .model import BaseModel


class Transaction:
    _model_cache: ModelCache
    _query_cache: QueryCache

    def __init__(self):
        self._model_cache = ModelCache()
        self._query_cache = QueryCache()
