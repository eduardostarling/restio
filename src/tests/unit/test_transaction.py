from typing import List, Tuple, Optional
from .base import TestBase
from random import randint
from uuid import uuid4
import asyncio

from restio.model import BaseModel, PrimaryKey, ValueKey, mdataclass, pk
from restio.state import ModelState
from restio.query import query
from restio.dao import BaseDAO
from restio.transaction import Transaction, TransactionError, PersistencyStrategy
from restio.graph import DependencyGraph, NavigationDirection

caller = None


@mdataclass
class ModelA(BaseModel):
    key: PrimaryKey[int] = pk(int)
    v: int = 0
    s: str = ""
    ex: bool = False
    ref: Optional[BaseModel] = None


class ModelDAO(BaseDAO):
    async def add(self, obj):
        await asyncio.sleep(randint(1, 2) / 10000)
        return obj

    async def update(self, obj):
        await asyncio.sleep(randint(1, 2) / 10000)
        return obj

    async def remove(self, obj):
        await asyncio.sleep(randint(1, 2) / 10000)
        return obj


class ModelDAOException(ModelDAO):
    async def add(self, obj):
        ret = await super().add(obj)
        if ret.ex:
            raise Exception("Add exception")
        return ret

    async def update(self, obj):
        ret = await super().add(obj)
        if ret.ex:
            raise Exception("Update exception")
        return ret

    async def remove(self, obj):
        ret = await super().remove(obj)
        if ret.ex:
            raise Exception("Remove exception")
        return ret


@query
async def SimpleQuery(self, test_case: 'TestTransaction') -> List[ModelA]:
    global caller

    a = ModelA(key=PrimaryKey(int, 1), v=11)
    b = ModelA(key=PrimaryKey(int, 2), v=22, ref=a)
    c = ModelA(key=PrimaryKey(int, 3), v=33, ref=b)

    test_case.assertIsInstance(self, Transaction)
    test_case.assertEqual(caller, "BeforeCache")

    return [a, b, c]


@query
async def EmptyQuery(self, test_case: 'TestTransaction') -> List[ModelA]:
    test_case.assertIsInstance(self, Transaction)
    return []


class TestTransaction(TestBase):
    def get_models(self):
        """
        C(33)
          |
        B(22)
          |
        A(11)
        """
        a = ModelA(key=PrimaryKey(int, 1), v=11)
        b = ModelA(key=PrimaryKey(int, 2), v=22, ref=a)
        c = ModelA(key=PrimaryKey(int, 3), v=33, ref=b)

        return (a, b, c)

    def get_models_complex(self):
        r"""
        F(66)   E(55)   C(33)
           \     /        |
            D(44)       B(22)
                          |
                        A(11)
        """

        a, b, c = self.get_models()
        d = ModelA(key=PrimaryKey(int, 4), v=44)
        e = ModelA(key=PrimaryKey(int, 5), v=55, ref=d)
        f = ModelA(key=PrimaryKey(int, 6), v=66, ref=d)

        return (a, b, c, d, e, f)

    def get_models_strategy(self):
        """
        A   C   E   G   I
        |   |   |   |   |
        B   D   F   H   J
        """
        b = ModelA(key=PrimaryKey(int, 2), v=22)
        a = ModelA(key=PrimaryKey(int, 1), v=11, ref=b)
        d = ModelA(key=PrimaryKey(int, 4), v=44, ex=True)
        c = ModelA(key=PrimaryKey(int, 3), v=33, ref=d)
        f = ModelA(key=PrimaryKey(int, 6), v=66)
        e = ModelA(key=PrimaryKey(int, 5), v=55, ref=f)
        h = ModelA(key=PrimaryKey(int, 8), v=88)
        g = ModelA(key=PrimaryKey(int, 7), v=77, ref=h)
        j = ModelA(key=PrimaryKey(int, 10), v=100)
        i = ModelA(key=PrimaryKey(int, 9), v=99, ref=j)

        models = tuple([a, b, c, d, e, f, g, h, i, j])

        for model in models[0:6]:
            model._state = ModelState.DIRTY

        # To add
        g._state = ModelState.NEW
        h._state = ModelState.NEW

        # To remove
        i._state = ModelState.DELETED
        j._state = ModelState.DELETED

        return models

    def test_init(self):
        x = Transaction()

        self.assertDictEqual(x._model_cache._cache, {})
        self.assertDictEqual(x._query_cache._cache, {})

    @TestBase.async_test
    async def test_register_model(self):
        a = ModelA(key=PrimaryKey(int, 1), v=11)
        b = ModelA(key=PrimaryKey(int, 2), v=22)

        x = Transaction()
        x.register_model(a)
        x.register_model(b)
        x.register_model(None)

        self.assertEqual(len(x._model_cache._cache.values()), 2)
        self.assertEqual(await x.get(ModelA, 1), a)
        self.assertEqual(await x.get(ModelA, 2), b)

        return a, b, x

    @TestBase.async_test
    async def test_force_register_model(self):
        old_a = ModelA(key=PrimaryKey(int, 1), v=11)
        old_b = ModelA(key=PrimaryKey(int, 2), v=22)
        a = ModelA(key=PrimaryKey(int, 1), v=33)
        b = ModelA(key=PrimaryKey(int, 2), v=44)

        x = Transaction()
        x.register_model(old_a)
        x.register_model(old_b)
        x.register_model(a)
        x.register_model(b)

        self.assertEqual(await x.get(ModelA, 1), old_a)
        self.assertEqual(await x.get(ModelA, 2), old_b)
        self.assertNotEqual(await x.get(ModelA, 1), a)
        self.assertNotEqual(await x.get(ModelA, 2), b)

        x.register_model(a, True)
        x.register_model(b, True)

        self.assertNotEqual(await x.get(ModelA, 1), old_a)
        self.assertNotEqual(await x.get(ModelA, 2), old_b)
        self.assertEqual(await x.get(ModelA, 1), a)
        self.assertEqual(await x.get(ModelA, 2), b)

    @TestBase.async_test
    async def test_register_model_and_children(self):
        a, b, c = self.get_models()

        x = Transaction()
        x.register_model(c)

        self.assertEqual(await x.get(ModelA, 1), a)
        self.assertEqual(await x.get(ModelA, 2), b)
        self.assertEqual(await x.get(ModelA, 3), c)

        y = Transaction()
        with self.assertRaises(RuntimeError):
            y.register_model(c, register_children=False)

        return a, b, c, x

    @TestBase.async_test
    async def test_force_register_model_and_children(self):
        old_a, old_b, old_c = self.get_models()
        a, b, c = self.get_models()

        x = Transaction()
        x.register_model(old_c)
        x.register_model(c)

        self.assertEqual(await x.get(ModelA, 1), old_a)
        self.assertEqual(await x.get(ModelA, 2), old_b)
        self.assertEqual(await x.get(ModelA, 3), old_c)
        self.assertNotEqual(await x.get(ModelA, 1), a)
        self.assertNotEqual(await x.get(ModelA, 2), b)
        self.assertNotEqual(await x.get(ModelA, 3), c)

        x.register_model(c, True)

        self.assertNotEqual(await x.get(ModelA, 1), old_a)
        self.assertNotEqual(await x.get(ModelA, 2), old_b)
        self.assertNotEqual(await x.get(ModelA, 3), old_c)
        self.assertEqual(await x.get(ModelA, 1), a)
        self.assertEqual(await x.get(ModelA, 2), b)
        self.assertEqual(await x.get(ModelA, 3), c)

    @TestBase.async_test
    async def test_get_cached(self):
        a, b, c = self.get_models()

        x = Transaction()
        x._model_cache.register(a)
        x._model_cache.register(b)
        x._model_cache.register(c)

        self.assertEqual(await x.get(ModelA, 1), a)
        self.assertEqual(await x.get(ModelA, 2), b)
        self.assertEqual(await x.get(ModelA, 3), c)

    @TestBase.async_test
    async def test_get_cached_reset(self):
        a, _, _ = self.get_models()
        query = EmptyQuery(self)

        x = Transaction()
        x.register_model(a)
        x.register_query(query, await query(x))

        self.assertEqual(await x.get(ModelA, 1), a)
        self.assertEqual(await x.query(query), [])

        x.reset()
        self.assertDictEqual(x._model_cache._cache, {})
        self.assertDictEqual(x._query_cache._cache, {})

        # after reset, the transaction must try to call
        # the DAO since "a" has been cleared
        with self.assertRaises(RuntimeError):
            await x.get(ModelA, 1)

    @TestBase.async_test
    async def test_get_new(self):
        a, b, c = self.get_models()

        class ModelADAO(BaseDAO):
            _model_type = ModelA

            async def get(self, obj: Tuple[ValueKey]):
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

        self.assertEqual(await x.get(ModelA, 1), a)
        self.assertEqual(await x.get(ModelA, [2]), b)
        self.assertEqual(await x.get(ModelA, 3), c)
        self.assertEqual(await x.get(ModelA, 4), None)

        self.assertEqual(a._state, ModelState.CLEAN)
        self.assertEqual(b._state, ModelState.CLEAN)
        self.assertEqual(c._state, ModelState.CLEAN)

    @TestBase.async_test
    async def test_get_invalid_dao(self):
        x = Transaction()
        with self.assertRaises(RuntimeError):
            await x.get(ModelA, 1)

    @TestBase.async_test
    async def test_get_not_implemented(self):
        x = Transaction()
        x.register_dao(BaseDAO(BaseModel))
        with self.assertRaises(RuntimeError):
            await x.get(BaseModel, 1)

    @TestBase.async_test
    async def test_query(self):
        global caller

        x = Transaction()
        q = SimpleQuery(self)

        # performs query
        caller = "BeforeCache"
        a, b, c = tuple(await x.query(q))

        self.assertEqual(await x.get(ModelA, 1), a)
        self.assertEqual(await x.get(ModelA, 2), b)
        self.assertEqual(await x.get(ModelA, 3), c)

        # retrieves from cache
        caller = "AfterCache"
        a, b, c = tuple(await x.query(q))

        self.assertEqual(await x.get(ModelA, 1), a)
        self.assertEqual(await x.get(ModelA, 2), b)
        self.assertEqual(await x.get(ModelA, 3), c)

    @TestBase.async_test
    async def test_empty_query(self):
        x = Transaction()
        q = EmptyQuery(self)

        self.assertEqual(await x.query(q), [])

    def test_assert_cache_internal_id(self):
        x = Transaction()
        with self.assertRaises(RuntimeError):
            x._assert_cache_internal_id(ModelA())

    @TestBase.async_test
    async def test_add(self):
        x = Transaction()
        a, _, _ = self.get_models()
        a_copy = a.copy()
        a_copy._internal_id = uuid4()

        self.assertTrue(x.add(a))

        with self.assertRaises(RuntimeError):
            x.add(a)

        with self.assertRaises(RuntimeError):
            x.add(a_copy)

        cached_a = await x.get(ModelA, 1)

        self.assertEqual(cached_a, a)
        self.assertEqual(cached_a._state, ModelState.NEW)

    @TestBase.async_test
    async def test_update(self):
        x = Transaction()
        a, _, _ = self.get_models()
        old_a_value = a.v

        x.register_model(a)
        cached_a = await x.get(ModelA, 1)

        self.assertEqual(cached_a, a)
        self.assertEqual(cached_a._state, ModelState.CLEAN)

        a.v = 100
        x.update(a)

        cached_a = await x.get(ModelA, 1)

        self.assertEqual(cached_a._state, ModelState.DIRTY)
        self.assertEqual(cached_a.v, 100)
        self.assertDictEqual(cached_a._persistent_values, {'v': old_a_value})

        return x, a, old_a_value

    @TestBase.async_test
    async def test_update_twice(self):
        x = Transaction()
        a, _, _ = self.get_models()
        old_a_value = a.v
        old_a_string = a.s

        x.register_model(a)

        a.v = 100
        x.update(a)

        a.v = old_a_value
        a.s = "string"
        x.update(a)

        cached_a = await x.get(ModelA, 1)

        self.assertEqual(cached_a._state, ModelState.DIRTY)
        self.assertEqual(cached_a.v, old_a_value)
        self.assertEqual(cached_a.s, "string")
        self.assertDictEqual(cached_a._persistent_values, {'s': old_a_string})

        return x, a, old_a_value, old_a_string

    @TestBase.async_test
    async def test_update_to_persistent(self):
        x = Transaction()
        a, _, _ = self.get_models()
        old_a_value = a.v
        old_a_string = a.s

        x.register_model(a)

        a.v = 100
        a.s = "string"
        x.update(a)

        a.v = old_a_value
        a.s = old_a_string

        x.update(a)

        cached_a = await x.get(ModelA, 1)

        self.assertEqual(cached_a._state, ModelState.CLEAN)
        self.assertEqual(cached_a.v, old_a_value)
        self.assertEqual(cached_a.s, old_a_string)
        self.assertDictEqual(cached_a._persistent_values, {})

    @TestBase.async_test
    async def test_update_new(self):
        x = Transaction()
        a, _, _ = self.get_models()

        x.add(a)
        cached_a = await x.get(ModelA, 1)

        self.assertEqual(cached_a, a)
        self.assertEqual(cached_a._state, ModelState.NEW)

        a.v = 100
        x.update(a)

        cached_a = await x.get(ModelA, 1)

        self.assertEqual(cached_a._state, ModelState.NEW)
        self.assertEqual(cached_a.v, 100)
        self.assertDictEqual(cached_a._persistent_values, {})

    @TestBase.async_test
    async def test_remove(self):
        x = Transaction()
        a, _, _ = self.get_models()

        x.register_model(a)
        cached_a = await x.get(ModelA, 1)

        self.assertEqual(cached_a, a)
        self.assertEqual(cached_a._state, ModelState.CLEAN)

        x.remove(a)

        cached_a = await x.get(ModelA, 1)

        self.assertEqual(cached_a._state, ModelState.DELETED)

    def test_check_deleted_models(self):
        a, b, c = models = self.get_models()
        a._state = ModelState.DELETED
        b._state = ModelState.DELETED

        x = Transaction()
        with self.assertRaises(RuntimeError):
            x._check_deleted_models(models)

        c._state = ModelState.DELETED
        x._check_deleted_models()

    @TestBase.async_test
    async def test_commit(self):
        for i in range(30):
            models = set(self.get_models_complex())

            x = Transaction()
            x.register_dao(ModelDAO(ModelA))

            states = [ModelState.NEW, ModelState.DIRTY, ModelState.DELETED]

            for model in models:
                model._state = states[randint(0, len(states) - 1)]

            for model in models:
                x.register_model(model)

            await x.commit()

            models_in_cache = x._model_cache._cache.values()

            for model in models_in_cache:
                self.assertEqual(model._state, ModelState.CLEAN)
                self.assertDictEqual(model._persistent_values, {})

            models_removed = set(filter(lambda m: m._state == ModelState.DELETED, models))
            self.assertEqual(len(set(models_in_cache).intersection(models_removed)), 0)

    @TestBase.async_test
    async def test_commit_exception(self):
        a, b, c, d, e, f = models = list(self.get_models_complex())

        x = Transaction(strategy=PersistencyStrategy.INTERRUPT_ON_ERROR)
        x.register_dao(ModelDAOException(ModelA))

        f._state = ModelState.NEW
        e._state = ModelState.NEW
        d._state = ModelState.DIRTY
        b._state = ModelState.DELETED
        a._state = ModelState.DELETED
        a.ex = True

        for model in models:
            x.register_model(model)

        with self.assertRaises(TransactionError) as error:
            await x.commit()

        ex = error.exception

        a_cache, b_cache = [x._model_cache.get_by_internal_id(ModelA, y._internal_id) for y in [a, b]]
        self.assertIsNone(b_cache)
        self.assertIsNotNone(a_cache)
        self.assertEqual(a_cache._state, ModelState.DELETED)

        self.assertSetEqual(set(ex.models), set([f, e, d, b]))
        self.assertEqual(len(ex.errors), 1)
        self.assertEqual(ex.errors[0].model, a)

    @TestBase.async_test
    async def _check_exception_strategies(self, models, strategy, expected):
        x = Transaction(strategy=strategy)
        x.register_dao(ModelDAOException(ModelA))

        for model in models:
            x.register_model(model)

        with self.assertRaises(TransactionError) as error:
            await x.commit()

        ex = error.exception
        expected_processed, maybe_processed, expected_errors, expected_not_processed = expected
        processed_models = set(ex.models)
        error_models = set([e.model for e in ex.errors])
        pending_models = x.get_transaction_models()

        # A model that may have been processed is either processed or
        # pending. Intersecting both processed and pending lists should
        # then cover them all
        expected_processed_or_pending = maybe_processed.intersection(processed_models).union(
            maybe_processed.intersection(pending_models)
        )

        self.assertEqual(expected_processed.intersection(processed_models), expected_processed)
        self.assertEqual(maybe_processed, expected_processed_or_pending)
        self.assertSetEqual(expected_errors, error_models)
        self.assertSetEqual(expected_not_processed, pending_models)

    def test_commit_exception_interrupt_on_error(self):
        a, b, c, d, e, f, g, h, i, j = models = self.get_models_strategy()

        processed_when_canceled = set([b, e, g, h])
        maybe_processed_when_canceled = set([a, e])
        errors_when_canceled = set([d])
        not_processed_when_canceled = set([c, d, i, j])
        expected_canceled = (processed_when_canceled, maybe_processed_when_canceled,
                             errors_when_canceled, not_processed_when_canceled)

        self._check_exception_strategies(models, PersistencyStrategy.INTERRUPT_ON_ERROR, expected_canceled)

    def test_commit_exception_continue_on_error(self):
        a, b, c, d, e, f, g, h, i, j = models = self.get_models_strategy()

        processed_when_ignored = set(models).difference(set([d]))
        maybe_processed_when_ignored = set()
        errors_when_ignored = set([d])
        not_processed_when_ignored = errors_when_ignored
        expected_ignored = (processed_when_ignored, maybe_processed_when_ignored,
                            errors_when_ignored, not_processed_when_ignored)

        self._check_exception_strategies(models, PersistencyStrategy.CONTINUE_ON_ERROR, expected_ignored)

    @TestBase.async_test
    async def test_process_all_trees(self):
        models = set(self.get_models_complex())

        x = Transaction()
        x.register_dao(ModelDAO(ModelA))

        for model in models:
            model._state = ModelState.NEW

        y = DependencyGraph.generate_from_objects(models)

        processed_models = await x._process_all_trees(y, NavigationDirection.LEAFS_TO_ROOTS)
        models = models.difference(set(processed_models))

        self.assertEqual(len(models), 0)

    @TestBase.async_test
    async def test_process_tree(self):
        a, b, c = self.get_models()

        x = Transaction()
        x.register_dao(ModelDAO(ModelA))

        models = list([a, b, c])
        for model in models:
            model._state = ModelState.NEW

        y = DependencyGraph.generate_from_objects(models)

        processed_models = list(reversed(await x._process_tree(y.trees[0], NavigationDirection.LEAFS_TO_ROOTS)))

        self.assertListEqual(models, processed_models)

    @TestBase.async_test
    async def test_get_models_callables(self):
        a, b, c = self.get_models()

        x = Transaction()
        x.register_dao(ModelDAO(ModelA))

        models = set([a, b, c])
        y = DependencyGraph.generate_from_objects(models)
        tree = y.trees[0]

        for state in (ModelState.NEW, ModelState.DIRTY, ModelState.DELETED):
            for model in models:
                model._state = state

            for node, coroutine in x._get_nodes_callables(tree.get_nodes()).items():
                node_return, model_return = await coroutine()
                self.assertEqual(node.node_object, model_return)
                self.assertEqual(node, node_return)

    @TestBase.async_test
    async def test_rollback(self):
        a, b, c, d, e, f = models = list(self.get_models_complex())
        x = Transaction()

        x.register_model(a)
        x.register_model(d)
        x.register_model(f)
        x.add(b)
        x.add(c)
        x.add(e)
        x.remove(f)

        d.v = 444
        x.update(d)

        a_cache, b_cache, c_cache, d_cache, e_cache, f_cache = \
            [await x.get(m.__class__, m.get_keys()) for m in models]

        self.assertEqual(a_cache._state, ModelState.CLEAN)
        self.assertEqual(b_cache._state, ModelState.NEW)
        self.assertEqual(c_cache._state, ModelState.NEW)
        self.assertEqual(d_cache._state, ModelState.DIRTY)
        self.assertEqual(e_cache._state, ModelState.NEW)
        self.assertEqual(f_cache._state, ModelState.DELETED)

        self.assertEqual(d_cache, d)
        self.assertEqual(d_cache.v, 444)

        x.rollback()

        a_cache = await x.get(a.__class__, a.get_keys())
        d_cache = await x.get(d.__class__, d.get_keys())

        for m in [b, c, e, f]:
            with self.assertRaises(RuntimeError):
                await x.get(m.__class__, m.get_keys())

        self.assertEqual(a_cache._state, ModelState.CLEAN)
        self.assertEqual(d_cache._state, ModelState.CLEAN)

        self.assertEqual(a_cache, a)
        self.assertEqual(d_cache, d)
        self.assertEqual(d_cache.v, 44)
