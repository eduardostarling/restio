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

