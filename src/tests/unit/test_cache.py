from typing import List
from .base import TestBase

from restio.model import BaseModel, PrimaryKey, pk, mdataclass
from restio.query import query
from restio.cache import ModelCache, QueryCache


@mdataclass
class Model(BaseModel):
    id: PrimaryKey[int] = pk(int)


@query
async def SimpleQuery(self) -> List[Model]:
    m1 = Model(id=PrimaryKey(int, 1))
    m2 = Model(id=PrimaryKey(int, 2))
    return [m1, m2]


@query
async def ArgsQuery(self, arg1: int, arg2: int = 2) -> List[BaseModel]:
    m1 = Model(id=PrimaryKey(int, arg1))
    m2 = Model(id=PrimaryKey(int, arg2))
    return [m1, m2]


class TestModelCache(TestBase):

    def setUp(self):
        self.x = ModelCache()
        self.m = Model()

    def test_init(self):
        self.assertDictEqual(self.x._cache, {})

    def test_register_unique_internal_id(self):
        # Checks if model does not exist in cache
        self.assertIsNone(self.x.get_by_internal_id(Model, self.m._internal_id))
        # Registers model in cache
        self.assertTrue(self.x.register(self.m))
        # Tries to register the same model again
        self.assertFalse(self.x.register(self.m))

    def test_register_unique_primary_key(self):
        # Model with unique key 1
        m2 = Model()
        m2.set_keys(1)

        # Model with duplicated key 1
        m3 = Model()
        m3.set_keys(1)

        # Registers model with unique key 1
        self.assertTrue(self.x.register(m2))

        # Tries to register same model and different model
        # with same primary key
        self.assertFalse(self.x.register(m2))
        self.assertFalse(self.x.register(m3))

    def test_register_force(self):
        # Model with unique key 1
        m2 = Model()
        m2.set_keys(1)

        # Model with duplicated key 1
        m3 = Model()
        m3.set_keys(1)

        # Registers model with unique key 1
        self.assertTrue(self.x.register(m2))

        # Tries to register same model and different model
        # with same primary key
        self.assertTrue(self.x.register(m2, True))
        self.assertTrue(self.x.register(m3, True))

    def test_unregister(self):
        m2 = Model()
        m2.set_keys(1)

        m3 = Model()
        m3.set_keys(2)

        m4 = Model()
        m4.set_keys(3)

        self.assertTrue(self.x.register(m2))
        self.assertTrue(self.x.register(m3))

        self.x.unregister(m2)
        with self.assertRaises(ValueError):
            self.x.unregister(m4)

        self.assertEqual(len(self.x._cache.values()), 1)

    def test_get_type(self):
        self.x = ModelCache()

        self.assertEqual(len(self.x.get_type(Model)), 0)
        self.test_register_unique_internal_id()
        self.assertEqual(len(self.x.get_type(Model)), 1)

        self.x = ModelCache()

        self.assertEqual(len(self.x.get_type(Model)), 0)
        self.test_register_unique_primary_key()
        self.assertEqual(len(self.x.get_type(Model)), 1)

    def test_get_by_internal_id(self):
        self.test_register_unique_internal_id()
        # Checks if model now exists in cache
        c = self.x.get_by_internal_id(Model, self.m._internal_id)
        self.assertIsNotNone(c)
        # Checks if another type does not exist in cache
        self.assertIsNone(self.x.get_by_internal_id(BaseModel, "fake"))

    def test_get(self):
        self.test_register_unique_primary_key()
        # Checks if model now exists in cache
        self.assertIsNotNone(self.x.get(Model, (1,)))
        # Checks if another type does not exist in cache
        self.assertIsNone(self.x.get(BaseModel, (1,)))

    def test_get_key(self):
        m = Model()
        m.set_keys(1)

        self.x.register(m)
        first_ref = self.x.get_by_internal_id(Model, m._internal_id)
        second_ref = self.x.get(Model, m.id.get())
        third_ref = self.x.get(Model, [m.id])

        self.assertEqual(first_ref, second_ref)
        self.assertEqual(second_ref, third_ref)


class TestQueryCache(TestBase):
    @TestBase.async_test
    async def setUp(self):
        self.x = QueryCache()
        self.q = SimpleQuery
        self.qa = ArgsQuery(5, 6)
        self.qaa = ArgsQuery(5, 7)
        self.r = await self.q()
        self.ra = await self.qa()
        self.raa = await self.qaa()

    def test_init(self):
        self.assertDictEqual(self.x._cache, {})

    def test_register_noargs(self):
        self.assertTrue(self.x.register(self.q, self.r))
        self.assertFalse(self.x.register(self.q, self.r))

    def test_get_noargs(self):
        self.test_register_noargs()
        self.assertListEqual(self.x.get(self.q), self.r)
        self.assertListEqual(self.x.get(self.q.__hash__()), self.r)

    def test_register_args(self):
        self.assertTrue(self.x.register(self.qa, self.ra))
        self.assertFalse(self.x.register(self.qa, self.ra))

        self.assertTrue(self.x.register(self.qaa, self.raa))
        self.assertFalse(self.x.register(self.qaa, self.raa))
