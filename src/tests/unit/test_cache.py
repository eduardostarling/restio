import unittest

from integration.model import BaseModel
from integration.cache import ModelCache, QueryCache


class TestModelCache(unittest.TestCase):
    def test_init(self):
        x = ModelCache()
        self.assertDictEqual(x._cache, {})

    def test_register(self):
        pass

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
