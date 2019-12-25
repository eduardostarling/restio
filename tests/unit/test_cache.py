from typing import List

import pytest

from restio.cache import ModelCache, QueryCache
from restio.model import BaseModel, PrimaryKey, mdataclass
from restio.query import query


@mdataclass
class Model(BaseModel):
    id: PrimaryKey[int] = PrimaryKey(int)


@query
async def SimpleQuery(self) -> List[Model]:
    m1 = Model(id=1)
    m2 = Model(id=2)
    return [m1, m2]


@query
async def ArgsQuery(self, arg1: int, arg2: int = 2) -> List[BaseModel]:
    m1 = Model(id=arg1)
    m2 = Model(id=arg2)
    return [m1, m2]


class TestModelCache:
    def setup_method(self, method):
        self.x = ModelCache()
        self.m = Model()

    @pytest.fixture
    def cache(self):
        return ModelCache()

    def test_init(self, cache):
        assert cache._id_cache == {}
        assert cache._key_cache == {}

    def test_register_unique_internal_id(self, cache):
        # Checks if model does not exist in cache
        assert cache.get_by_internal_id(Model, self.m._internal_id) is None
        # Registers model in cache
        assert cache.register(self.m)
        # Tries to register the same model again
        assert not cache.register(self.m)

    def test_register_unique_primary_key(self, cache: ModelCache):
        # Model with unique key 1
        m2 = Model(id=1)

        # Model with duplicated key 1
        m3 = Model(id=1)

        # Registers model with unique key 1
        assert cache.register(m2)

        # Tries to register same model and different model
        # with same primary key
        assert not cache.register(m2)
        assert not cache.register(m3)

    def test_register_force(self, cache):
        # Model with unique key 1
        m2 = Model(id=1)
        # Model with duplicated key 1
        m3 = Model(id=1)

        # Registers model with unique key 1
        assert cache.register(m2)

        # Tries to register same model and different model
        # with same primary key
        assert cache.register(m2, True)
        assert cache.register(m3, True)

    def test_unregister(self, cache):
        m2 = Model(id=1)
        m3 = Model(id=2)
        m4 = Model(id=3)

        assert cache.register(m2)
        assert cache.register(m3)

        cache.unregister(m2)
        with pytest.raises(ValueError):
            cache.unregister(m4)

        assert len(cache._id_cache.values()) == 1
        assert len(cache._key_cache.values()) == 1

    def test_get_by_internal_id(self, cache):
        self.test_register_unique_internal_id(cache)
        # Checks if model now exists in cache
        c = cache.get_by_internal_id(Model, self.m._internal_id)
        assert c is not None
        # Checks if another type does not exist in cache
        assert cache.get_by_internal_id(BaseModel, "fake") is None

    def test_get(self, cache):
        self.test_register_unique_primary_key(cache)
        # Checks if model now exists in cache
        assert cache.get_by_primary_key(Model, (1,)) is not None
        # Checks if another type does not exist in cache
        assert cache.get_by_primary_key(BaseModel, (1,)) is None

    def test_get_by_primary_key(self, cache):
        m = Model()
        m.id = 1

        cache.register(m)
        first_ref = cache.get_by_primary_key(Model, (m.id,))

        assert first_ref == m


class TestQueryCache:

    @pytest.fixture
    def cache(self):
        return QueryCache()

    @pytest.fixture
    async def query_simple(self):
        q = SimpleQuery
        return q, await q()

    @pytest.fixture
    async def query_args_first(self):
        q = ArgsQuery(5, 6)
        return q, await q()

    @pytest.fixture
    async def query_args_second(self):
        q = ArgsQuery(5, 7)
        return q, await q()

    def test_init(self, cache):
        assert cache._cache == {}

    def test_register_noargs(self, cache, query_simple):
        q, r = query_simple
        assert cache.register(q, r)
        assert not cache.register(q, r)

    def test_get_noargs(self, cache, query_simple):
        self.test_register_noargs(cache, query_simple)
        q, r = query_simple
        assert cache.get(q) == r
        assert cache.get(q.__hash__()) == r

    def test_register_args(self, cache, query_args_first, query_args_second):
        qa, ra = query_args_first
        qaa, raa = query_args_second
        assert cache.register(qa, ra)
        assert not cache.register(qa, ra)

        assert cache.register(qaa, raa)
        assert not cache.register(qaa, raa)
