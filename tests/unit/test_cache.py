from typing import List, Tuple

import pytest

from restio.cache import ModelCache, QueryCache
from restio.fields import IntField
from restio.model import BaseModel
from restio.query import query


class Model(BaseModel):
    id: IntField = IntField(pk=True, default=1)

    def __init__(self, id_=None):
        self.id = id_ or self.id


@query
async def SimpleQuery(*, session) -> Tuple[Model, ...]:
    m1 = Model(id_=1)
    m2 = Model(id_=2)
    return (m1, m2)


@query
async def ArgsQuery(arg1: int, arg2: int = 2, *, session) -> List[BaseModel]:
    m1 = Model(id_=arg1)
    m2 = Model(id_=arg2)
    return [m1, m2]


class TestModelCache:
    @pytest.fixture
    def cache(self):
        return ModelCache()

    @pytest.fixture
    def m(self):
        return Model()

    def test_init(self, cache):
        assert cache._id_cache == set()
        assert cache._key_cache == {}

    def test_register_unique_internal_id(self, cache: ModelCache, m: Model):
        # Checks if model does not exist in cache
        assert not cache.is_registered_by_id(m)
        # Registers model in cache
        assert cache.register(m)
        assert cache.is_registered_by_id(m)
        # Tries to register the same model again
        assert not cache.register(m)

    def test_register_unique_primary_key(self, cache: ModelCache):
        # Model with unique key 1
        m2 = Model(id_=1)

        # Model with duplicated key 1
        m3 = Model(id_=1)

        # Registers model with unique key 1
        assert cache.register(m2)

        # Tries to register same model and different model
        # with same primary key
        assert not cache.register(m2)
        assert not cache.register(m3)

    def test_has_model_with_keys(self, cache: ModelCache):
        m2 = Model(id_=1)
        m3 = Model(id_=1)

        assert cache.register(m2)
        assert cache.has_model_with_keys(m2)
        assert cache.has_model_with_keys(m3)

    def test_has_keys(self, cache: ModelCache):
        m2 = Model(id_=1)

        assert cache.register(m2)
        assert cache.has_keys(cache._get_type_key_hash(m2))

    def test_register_force(self, cache: ModelCache):
        # Model with unique key 1
        m2 = Model(id_=1)
        # Model with duplicated key 1
        m3 = Model(id_=1)

        # Registers model with unique key 1
        assert cache.register(m2)

        # Tries to register same model and different model
        # with same primary key
        assert cache.register(m2, True)
        assert cache.register(m3, True)

    def test_unregister(self, cache: ModelCache):
        m2 = Model(id_=1)
        m3 = Model(id_=2)
        m4 = Model(id_=3)

        assert cache.register(m2)
        assert cache.register(m3)

        cache.unregister(m2)
        with pytest.raises(ValueError):
            cache.unregister(m4)

        assert len(cache._id_cache) == 1
        assert len(cache._key_cache.values()) == 1

    def test_get(self, cache: ModelCache):
        self.test_register_unique_primary_key(cache)
        # Checks if model now exists in cache
        assert cache.get_by_primary_key((Model, (1,))) is not None
        # Checks if another type does not exist in cache
        assert cache.get_by_primary_key((BaseModel, (1,))) is None

    def test_get_by_primary_key(self, cache: ModelCache, m: Model):
        m.id = 1

        cache.register(m)
        first_ref = cache.get_by_primary_key((Model, (m.id,)))

        assert first_ref == m


class TestQueryCache:
    @pytest.fixture
    def cache(self):
        return QueryCache()

    @pytest.fixture
    async def query_simple(self):
        q = SimpleQuery()
        return q, await q("session")  # type: ignore

    @pytest.fixture
    async def query_args_first(self):
        q = ArgsQuery(5, 6)
        return q, await q("session")  # type: ignore

    @pytest.fixture
    async def query_args_second(self):
        q = ArgsQuery(5, 7)
        return q, await q("session")  # type: ignore

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

    def test_register_args(self, cache, query_args_first, query_args_second):
        qa, ra = query_args_first
        qaa, raa = query_args_second
        assert cache.register(qa, ra)
        assert not cache.register(qa, ra)

        assert cache.register(qaa, raa)
        assert not cache.register(qaa, raa)
