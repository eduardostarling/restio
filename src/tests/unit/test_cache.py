import unittest

from integration.model import BaseModel, PrimaryKey
from integration.cache import ModelCache, QueryCache


class Model(BaseModel):
    id: PrimaryKey[int]


class TestModelCache(unittest.TestCase):

    def setUp(self):
        self.x = ModelCache()
        self.m = Model()

    def test_init(self):
        self.assertDictEqual(self.x._cache, {})

    def test_register_unique_internal_id(self):
        # Checks if model does not exist in cache
        self.assertIsNone(self.x.get_by_internal_id(Model, self.m.__hash__()))
        # Registers model in cache
        self.assertTrue(self.x.register(self.m))
        # Tries to register the same model again
        self.assertFalse(self.x.register(self.m))

    def test_register_unique_primary_key(self):
        # Model with unique key 1
        m2 = Model()
        m2.set_key(1)

        # Model with duplicated key 1
        m3 = Model()
        m3.set_key(1)

        # Registers model with unique key 1
        self.assertTrue(self.x.register(m2))

        # Tries to register same model and different model
        # with same primary key
        self.assertFalse(self.x.register(m2))
        self.assertFalse(self.x.register(m3))

    def test_register_force(self):
        # Model with unique key 1
        m2 = Model()
        m2.set_key(1)

        # Model with duplicated key 1
        m3 = Model()
        m3.set_key(1)

        # Registers model with unique key 1
        self.assertTrue(self.x.register(m2))

        # Tries to register same model and different model
        # with same primary key
        self.assertTrue(self.x.register(m2, True))
        self.assertTrue(self.x.register(m3, True))

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
        self.assertIsNotNone(self.x.get_by_internal_id(Model, self.m.__hash__()))
        # Checks if another type does not exist in cache
        self.assertIsNone(self.x.get_by_internal_id(BaseModel, "fake"))

    def test_get(self):
        self.test_register_unique_primary_key()
        # Checks if model now exists in cache
        self.assertIsNotNone(self.x.get(Model, 1))
        # Checks if another type does not exist in cache
        self.assertIsNone(self.x.get(BaseModel, 1))

    def test_hash(self):
        self.assertEqual(str(self.m._internal_id), self.m.__hash__())

    def test_get_key(self):
        m = Model()
        m.set_key(1)

        self.x.register(m)
        first_ref = self.x.get_by_internal_id(Model, m.__hash__())
        second_ref = self.x.get(Model, m.id.get())
        third_ref = self.x.get(Model, m.id)

        self.assertEqual(first_ref, second_ref)
        self.assertEqual(second_ref, third_ref)


class TestQueryCache(unittest.TestCase):
    def test_init(self):
        x = QueryCache()
        self.assertDictEqual(x._cache, {})

    def test_register(self):
        pass

    def test_get(self):
        pass
