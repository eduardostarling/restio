import unittest

from integration.model import BaseModel
from integration.transaction import Transaction


class TestTransaction(unittest.TestCase):
    def test_init(self):
        x = Transaction()
        m = BaseModel()

        self.assertIsNone(x._model_cache.get(BaseModel, m.__hash__()))
        self.assertTrue(x._model_cache.register(m))
        self.assertIsNotNone(x._model_cache.get(BaseModel, m.__hash__()))
        self.assertFalse(x._model_cache.register(m))
        self.assertEqual(len(x._model_cache._cache[BaseModel.__name__]), 1)
