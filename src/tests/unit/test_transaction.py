import unittest
from typing import List, Tuple, Optional

from integration.model import BaseModel, PrimaryKey, ValueKey, mdataclass, pk
from integration.query import Query
from integration.dao import BaseDAO
from integration.transaction import Transaction

caller = None


@mdataclass
class ModelA(BaseModel):
    key: PrimaryKey[int] = pk(int)
    v: int = 0
    ref: Optional[BaseModel] = None


@Query
def SimpleQuery(self, test_case: 'TestTransaction') -> List[ModelA]:
    global caller

    a = ModelA(key=PrimaryKey(int, 1), v=11)
    b = ModelA(key=PrimaryKey(int, 2), v=22, ref=a)
    c = ModelA(key=PrimaryKey(int, 3), v=33, ref=b)

    test_case.assertIsInstance(self, Transaction)
    test_case.assertEqual(caller, "BeforeCache")

    return [a, b, c]


@Query
def EmptyQuery(self, test_case: 'TestTransaction') -> List[ModelA]:
    test_case.assertIsInstance(self, Transaction)
    return []


class TestTransaction(unittest.TestCase):
    def get_models(self):
        a = ModelA(key=PrimaryKey(int, 1), v=11)
        b = ModelA(key=PrimaryKey(int, 2), v=22, ref=a)
        c = ModelA(key=PrimaryKey(int, 3), v=33, ref=b)

        return (a, b, c)

    def test_init(self):
        x = Transaction()

        self.assertDictEqual(x._model_cache._cache, {})
        self.assertDictEqual(x._query_cache._cache, {})

    def test_register_model(self):
        a = ModelA(key=PrimaryKey(int, 1), v=11)
        b = ModelA(key=PrimaryKey(int, 2), v=22)

        x = Transaction()
        x.register_model(a)
        x.register_model(b)

        self.assertEqual(x.get(ModelA, 1), a)
        self.assertEqual(x.get(ModelA, 2), b)

        return a, b, x

    def test_force_register_model(self):
        old_a, old_b, x = self.test_register_model()

        a = ModelA(key=PrimaryKey(int, 1), v=33)
        b = ModelA(key=PrimaryKey(int, 2), v=44)

        x.register_model(a)
        x.register_model(b)

        self.assertEqual(x.get(ModelA, 1), old_a)
        self.assertEqual(x.get(ModelA, 2), old_b)
        self.assertNotEqual(x.get(ModelA, 1), a)
        self.assertNotEqual(x.get(ModelA, 2), b)

        x.register_model(a, True)
        x.register_model(b, True)

        self.assertNotEqual(x.get(ModelA, 1), old_a)
        self.assertNotEqual(x.get(ModelA, 2), old_b)
        self.assertEqual(x.get(ModelA, 1), a)
        self.assertEqual(x.get(ModelA, 2), b)

    def test_register_model_and_children(self):
        a, b, c = self.get_models()

        x = Transaction()
        x.register_model(c)

        self.assertEqual(x.get(ModelA, 1), a)
        self.assertEqual(x.get(ModelA, 2), b)
        self.assertEqual(x.get(ModelA, 3), c)

        return a, b, c, x

    def test_force_register_model_and_children(self):
        old_a, old_b, old_c, x = self.test_register_model_and_children()

        a, b, c = self.get_models()

        x.register_model(c)

        self.assertEqual(x.get(ModelA, 1), old_a)
        self.assertEqual(x.get(ModelA, 2), old_b)
        self.assertEqual(x.get(ModelA, 3), old_c)
        self.assertNotEqual(x.get(ModelA, 1), a)
        self.assertNotEqual(x.get(ModelA, 2), b)
        self.assertNotEqual(x.get(ModelA, 3), c)

        x.register_model(c, True)

        self.assertNotEqual(x.get(ModelA, 1), old_a)
        self.assertNotEqual(x.get(ModelA, 2), old_b)
        self.assertNotEqual(x.get(ModelA, 3), old_c)
        self.assertEqual(x.get(ModelA, 1), a)
        self.assertEqual(x.get(ModelA, 2), b)
        self.assertEqual(x.get(ModelA, 3), c)

    def test_get_cached(self):
        a, b, c = self.get_models()

        x = Transaction()
        x._model_cache.register(a)
        x._model_cache.register(b)
        x._model_cache.register(c)

        self.assertEqual(x.get(ModelA, 1), a)
        self.assertEqual(x.get(ModelA, 2), b)
        self.assertEqual(x.get(ModelA, 3), c)

    def test_get_cached_reset(self):
        a, _, _ = self.get_models()
        query = EmptyQuery(self)

        x = Transaction()
        x.register_model(a)
        x.register_query(query, query(x))

        self.assertEqual(x.get(ModelA, 1), a)
        self.assertEqual(x.query(query), [])

        x.reset()
        self.assertDictEqual(x._model_cache._cache, {})
        self.assertDictEqual(x._query_cache._cache, {})

        # after reset, the transaction must try to call
        # the DAO since "a" has been cleared
        with self.assertRaises(RuntimeError):
            x.get(ModelA, 1)

    def test_get_new(self):
        a, b, c = self.get_models()

        class ModelADAO(BaseDAO):
            _model_type = ModelA

            def get(self, obj: Tuple[ValueKey]):
                key = obj[0]

                if key == 1:
                    return a
                elif key == 2:
                    return b
                elif key == 3:
                    return c

                return None

        x = Transaction()
        x.register_dao(ModelADAO())

        self.assertEqual(x.get(ModelA, 1), a)
        self.assertEqual(x.get(ModelA, [2]), b)
        self.assertEqual(x.get(ModelA, 3), c)
        self.assertEqual(x.get(ModelA, 4), None)

    def test_get_invalid_dao(self):
        x = Transaction()
        with self.assertRaises(RuntimeError):
            x.get(ModelA, 1)

    def test_get_not_implemented(self):
        x = Transaction()
        x.register_dao(BaseDAO(BaseModel))
        with self.assertRaises(RuntimeError):
            x.get(BaseModel, 1)

    def test_query(self):
        global caller

        x = Transaction()
        q = SimpleQuery(self)

        # performs query
        caller = "BeforeCache"
        a, b, c = tuple(x.query(q))

        self.assertEqual(x.get(ModelA, 1), a)
        self.assertEqual(x.get(ModelA, 2), b)
        self.assertEqual(x.get(ModelA, 3), c)

        # retrieves from cache
        caller = "AfterCache"
        a, b, c = tuple(x.query(q))

        self.assertEqual(x.get(ModelA, 1), a)
        self.assertEqual(x.get(ModelA, 2), b)
        self.assertEqual(x.get(ModelA, 3), c)

    def test_empty_query(self):
        x = Transaction()
        q = EmptyQuery(self)

        self.assertEqual(x.query(q), [])
