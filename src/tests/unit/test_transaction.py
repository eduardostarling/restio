import unittest

from integration.model import BaseModel, PrimaryKey
from integration.transaction import Transaction


class TestTransaction(unittest.TestCase):
    def test_init(self):
        x = Transaction()

        self.assertDictEqual(x._model_cache._cache, {})
        self.assertDictEqual(x._query_cache._cache, {})

    def test_register_model(self):
        x = Transaction()
        m = BaseModel()

        self.assertIsNone(x._model_cache.get(BaseModel, m.__hash__()))
        self.assertTrue(x._model_cache.register(m))
        self.assertIsNotNone(x._model_cache.get(BaseModel, m.__hash__()))
        self.assertFalse(x._model_cache.register(m))
        self.assertEqual(len([obj for t, obj in x._model_cache._cache
                             if t == BaseModel.__name__]), 1)
