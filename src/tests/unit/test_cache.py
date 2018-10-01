import unittest

from integration.model import BaseModel, PrimaryKey
from integration.cache import ModelCache, QueryCache


class Model(BaseModel):
    id: PrimaryKey[int]


class TestModelCache(unittest.TestCase):
    def test_init(self):
        x = ModelCache()
        self.assertDictEqual(x._cache, {})

    def test_register(self):
        x = ModelCache()
        m = Model()

        m2 = Model()
        m2.set_key(1)

        m3 = Model()
        m3.set_key(1)

        self.assertIsNone(x.get_by_internal_id(Model, m.__hash__()))
        self.assertTrue(x.register(m))
        self.assertIsNotNone(x.get_by_internal_id(Model, m.__hash__()))
        self.assertFalse(x.register(m))

        self.assertEqual(len([obj for t, obj in x._cache
                             if t == Model.__name__]), 1)

        self.assertTrue(x.register(m2))
        self.assertIsNotNone(x.get(Model, 1))
        self.assertFalse(x.register(m2))
        self.assertFalse(x.register(m3))

        self.assertEqual(len([obj for t, obj in x._cache
                         if t == Model.__name__]), 2)

    def test_get(self):
        pass


class TestQueryCache(unittest.TestCase):
    def test_init(self):
        x = QueryCache()
        self.assertDictEqual(x._cache, {})

    def test_register(self):
        pass

    def test_get(self):
        pass
