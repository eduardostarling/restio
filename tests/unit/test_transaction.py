from __future__ import annotations

import asyncio
import itertools
from random import randint
from typing import List, Optional, Tuple

import pytest

from restio.dao import BaseDAO
from restio.graph import DependencyGraph, NavigationDirection
from restio.model import BaseModel, PrimaryKey, ValueKey, mdataclass
from restio.query import query
from restio.state import ModelState
from restio.transaction import DAOTask, PersistencyStrategy, Transaction

caller = None


@mdataclass
class ModelA(BaseModel):
    key: PrimaryKey[int] = PrimaryKey(int)
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
async def SimpleQuery(self, query_arg: TestTransaction) -> List[ModelA]:
    global caller

    a = ModelA(key=1, v=11)
    b = ModelA(key=2, v=22, ref=a)
    c = ModelA(key=3, v=33, ref=b)

    assert isinstance(query_arg, TestTransaction)
    assert isinstance(self, Transaction)
    assert caller == "BeforeCache"

    return [a, b, c]


@query
async def EmptyQuery(self, query_arg: TestTransaction) -> List[ModelA]:
    assert isinstance(query_arg, TestTransaction)
    assert isinstance(self, Transaction)

    return []


class ModelsFixture:
    @pytest.fixture
    def models(self):
        """
        C(33)
          |
        B(22)
          |
        A(11)
        """
        a = ModelA(key=1, v=11)
        b = ModelA(key=2, v=22, ref=a)
        c = ModelA(key=3, v=33, ref=b)

        return (a, b, c)

    new_models = models

    @pytest.fixture
    def models_complex(self, models):
        r"""
        F(66)   E(55)   C(33)
           \     /        |
            D(44)       B(22)
                          |
                        A(11)
        """

        a, b, c = models
        d = ModelA(key=4, v=44)
        e = ModelA(key=5, v=55, ref=d)
        f = ModelA(key=6, v=66, ref=d)

        return (a, b, c, d, e, f)

    @pytest.fixture
    def models_strategy(self):
        """
        A   C   E   G   I
        |   |   |   |   |
        B   D   F   H   J
        """
        b = ModelA(key=2, v=22)
        a = ModelA(key=1, v=11, ref=b)
        d = ModelA(key=4, v=44, ex=True)
        c = ModelA(key=3, v=33, ref=d)
        f = ModelA(key=6, v=66)
        e = ModelA(key=5, v=55, ref=f)
        h = ModelA(key=8, v=88)
        g = ModelA(key=7, v=77, ref=h)
        j = ModelA(key=10, v=100)
        i = ModelA(key=9, v=99, ref=j)

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


class TestDAOTask(ModelsFixture):
    pass


class TestTransaction(ModelsFixture):
    @pytest.fixture
    def t(self):
        return Transaction()

    def test_init(self, t):
        assert t._model_cache._id_cache == {}
        assert t._model_cache._key_cache == {}
        assert t._query_cache._cache == {}

    @pytest.mark.asyncio
    async def test_register_model(self, t):
        a = ModelA(key=1, v=11)
        b = ModelA(key=2, v=22)

        t.register_model(a)
        t.register_model(b)
        t.register_model(None)

        assert len(t._model_cache._id_cache.values()) == 2
        assert len(t._model_cache._key_cache.values()) == 2
        assert await t.get(ModelA, 1) == a
        assert await t.get(ModelA, 2) == b

    @pytest.mark.asyncio
    async def test_force_register_model(self, t):
        old_a = ModelA(key=1, v=11)
        old_b = ModelA(key=2, v=22)
        a = ModelA(key=1, v=33)
        b = ModelA(key=2, v=44)

        t.register_model(old_a)
        t.register_model(old_b)
        t.register_model(a)
        t.register_model(b)

        assert await t.get(ModelA, 1) == old_a
        assert await t.get(ModelA, 2) == old_b
        assert await t.get(ModelA, 1) != a
        assert await t.get(ModelA, 2) != b

        t.register_model(a, True)
        t.register_model(b, True)

        assert await t.get(ModelA, 1) != old_a
        assert await t.get(ModelA, 2) != old_b
        assert await t.get(ModelA, 1) == a
        assert await t.get(ModelA, 2) == b

    @pytest.mark.asyncio
    async def test_register_model_and_children(self, t, models):
        a, b, c = models
        t.register_model(c)

        assert await t.get(ModelA, 1) == a
        assert await t.get(ModelA, 2) == b
        assert await t.get(ModelA, 3) == c

        y = Transaction()
        with pytest.raises(RuntimeError):
            y.register_model(c, register_children=False)

    @pytest.mark.asyncio
    async def test_force_register_model_and_children(self, t, models, new_models):
        old_a, old_b, old_c = models
        a, b, c = new_models

        t.register_model(old_c)
        t.register_model(c)

        assert await t.get(ModelA, 1) == old_a
        assert await t.get(ModelA, 2) == old_b
        assert await t.get(ModelA, 3) == old_c
        assert await t.get(ModelA, 1) != a
        assert await t.get(ModelA, 2) != b
        assert await t.get(ModelA, 3) != c

        t.register_model(c, True)

        assert await t.get(ModelA, 1) != old_a
        assert await t.get(ModelA, 2) != old_b
        assert await t.get(ModelA, 3) != old_c
        assert await t.get(ModelA, 1) == a
        assert await t.get(ModelA, 2) == b
        assert await t.get(ModelA, 3) == c

    @pytest.mark.asyncio
    async def test_get_cached(self, t, models):
        a, b, c = models

        t._model_cache.register(a)
        t._model_cache.register(b)
        t._model_cache.register(c)

        assert await t.get(ModelA, 1) == a
        assert await t.get(ModelA, 2) == b
        assert await t.get(ModelA, 3) == c

    @pytest.mark.asyncio
    async def test_get_cached_reset(self, t, models):
        a, _, _ = models
        query = EmptyQuery(self)

        t.register_model(a)
        await t.register_query(query, await query(t))

        assert await t.get(ModelA, 1) == a
        assert await t.query(query) == []

        t.reset()
        assert t._model_cache._id_cache == {}
        assert t._model_cache._key_cache == {}
        assert t._query_cache._cache == {}

        # after reset, the transaction must try to call
        # the DAO since "a" has been cleared
        with pytest.raises(RuntimeError):
            await t.get(ModelA, 1)

    @pytest.mark.asyncio
    async def test_get_new(self, t, models):
        a, b, c = models

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

        t.register_dao(ModelADAO())

        assert await t.get(ModelA, 1) == a
        assert await t.get(ModelA, [2]) == b
        assert await t.get(ModelA, 3) == c
        assert await t.get(ModelA, 4) is None

        assert a._state == ModelState.CLEAN
        assert b._state == ModelState.CLEAN
        assert c._state == ModelState.CLEAN

    @pytest.mark.asyncio
    async def test_get_new_concurrent(self, t):
        class ModelDAO(BaseDAO):
            a = None

            async def get(self, obj):
                await asyncio.sleep(randint(1, 2) / 10000)
                model = ModelA(key=1)
                if not ModelDAO.a:
                    ModelDAO.a = model
                return model

        t.register_dao(ModelDAO(ModelA))

        tasks = [t.get(ModelA, 1) for _ in range(5)]
        for task in asyncio.as_completed(tasks):
            result = await task
            assert result._internal_id == ModelDAO.a._internal_id

    @pytest.mark.asyncio
    async def test_get_invalid_dao(self, t):
        with pytest.raises(RuntimeError):
            await t.get(ModelA, 1)

    @pytest.mark.asyncio
    async def test_get_not_implemented(self, t):
        t.register_dao(BaseDAO(BaseModel))
        with pytest.raises(RuntimeError):
            await t.get(BaseModel, 1)

    @pytest.mark.asyncio
    async def test_query(self, t):
        global caller

        q = SimpleQuery(self)

        # performs query
        caller = "BeforeCache"
        a, b, c = tuple(await t.query(q))

        assert await t.get(ModelA, 1) == a
        assert await t.get(ModelA, 2) == b
        assert await t.get(ModelA, 3) == c

        # retrieves from cache
        caller = "AfterCache"
        a, b, c = tuple(await t.query(q))

        assert await t.get(ModelA, 1) == a
        assert await t.get(ModelA, 2) == b
        assert await t.get(ModelA, 3) == c

    @pytest.mark.asyncio
    async def test_query_with_existing_models(self, t, models):
        global caller
        a, *_ = models

        q = SimpleQuery(self)
        new_value = "new value to check query and model caches"
        a.s = new_value

        # value now exists in cache before the query is executed
        t.register_model(a)
        model_cached_a = await t.get(ModelA, 1)

        caller = "BeforeCache"
        q_result = await t.query(q)

        # previous value cached should be the one returned
        assert model_cached_a in q_result
        assert model_cached_a.s == new_value

    @pytest.mark.asyncio
    async def test_empty_query(self, t):
        q = EmptyQuery(self)
        assert await t.query(q) == []

    def test_assert_cache_internal_id(self, t):
        with pytest.raises(RuntimeError):
            t._assert_cache_internal_id(ModelA())

    @pytest.mark.asyncio
    async def test_add(self, t, models):
        a, _, _ = models

        assert t.add(a)
        with pytest.raises(RuntimeError):
            t.add(a)

        cached_a = await t.get(ModelA, 1)

        assert cached_a == a
        assert cached_a._state == ModelState.NEW

    @pytest.mark.asyncio
    async def test_update(self, t, models):
        a, _, _ = models
        old_a_value = a.v

        t.register_model(a)
        cached_a = await t.get(ModelA, 1)

        assert cached_a == a
        assert cached_a._state == ModelState.CLEAN

        a.v = 100
        cached_a = await t.get(ModelA, 1)

        assert cached_a._state == ModelState.DIRTY
        assert cached_a.v == 100
        assert cached_a._persistent_values == {'v': old_a_value}

    @pytest.mark.asyncio
    async def test_update_twice(self, t, models):
        a, _, _ = models
        old_a_value = a.v
        old_a_string = a.s

        t.register_model(a)

        a.v = 100
        a.v = old_a_value
        a.s = "string"

        cached_a = await t.get(ModelA, 1)

        assert cached_a._state == ModelState.DIRTY
        assert cached_a.v == old_a_value
        assert cached_a.s == "string"
        assert cached_a._persistent_values == {'s': old_a_string}

    @pytest.mark.asyncio
    async def test_update_to_persistent(self, t, models):
        a, _, _ = models
        old_a_value = a.v
        old_a_string = a.s

        t.register_model(a)

        a.v = 100
        a.s = "string"
        a.v = old_a_value
        a.s = old_a_string

        cached_a = await t.get(ModelA, 1)

        assert cached_a._state == ModelState.CLEAN
        assert cached_a.v == old_a_value
        assert cached_a.s == old_a_string
        assert cached_a._persistent_values == {}

    @pytest.mark.asyncio
    async def test_update_new(self, t, models):
        a, _, _ = models

        t.add(a)
        cached_a = await t.get(ModelA, 1)

        assert cached_a == a
        assert cached_a._state == ModelState.NEW

        a.v = 100
        cached_a = await t.get(ModelA, 1)

        assert cached_a._state == ModelState.NEW
        assert cached_a.v == 100
        assert cached_a._persistent_values == {}

    @pytest.mark.asyncio
    async def test_commit_new_primary_key(self, t, models):
        a, _, _ = models
        old_key = a.key

        class ModelADAO(BaseDAO):
            async def get(self, obj: Tuple[ValueKey]):
                if obj[0] == old_key:
                    return None
                else:
                    raise ValueError(
                        "Request using the new key did not return from cache.")

            async def update(self, obj):
                pass

        t.register_dao(ModelADAO(ModelA))
        t.register_model(a)

        a.key = 11
        # try getting the model by its old key
        cached_a = await t.get(ModelA, old_key)
        assert cached_a == a

        # the commit should always remap the primary keys
        await t.commit()
        # this should return None
        wrong_cached_a = await t.get(ModelA, old_key)
        # this should return the model from the cache
        correct_cached_a = await t.get(ModelA, a.key)

        assert not wrong_cached_a
        assert correct_cached_a == a


    @pytest.mark.asyncio
    async def test_remove(self, t, models):
        a, _, _ = models

        t.register_model(a)
        cached_a = await t.get(ModelA, 1)

        assert cached_a == a
        assert cached_a._state == ModelState.CLEAN

        t.remove(a)

        cached_a = await t.get(ModelA, 1)

        assert cached_a._state == ModelState.DELETED

    def test_check_deleted_models(self, t, models):
        a, b, c = models
        a._state = ModelState.DELETED
        b._state = ModelState.DELETED

        with pytest.raises(RuntimeError):
            t._check_deleted_models(models)

        c._state = ModelState.DELETED
        t._check_deleted_models()

    commit_iterations = itertools.product(
        [ModelState.NEW, ModelState.DIRTY, ModelState.DELETED],
        repeat=6)

    @pytest.mark.parametrize('states', commit_iterations)
    @pytest.mark.asyncio
    async def test_commit(self, t, models_complex, states):
        models = set(models_complex)
        t.register_dao(ModelDAO(ModelA))

        for index, model in enumerate(models):
            model._state = states[index]

        for model in models:
            t.register_model(model)

        await t.commit()

        models_in_cache = t._model_cache.get_all_models()

        for model in models_in_cache:
            assert model._state == ModelState.CLEAN
            assert model._persistent_values == {}

        models_removed = set(filter(lambda m: m._state == ModelState.DELETED, models))
        assert len(set(models_in_cache).intersection(models_removed)) == 0

    @pytest.mark.asyncio
    async def test_commit_exception(self, models_complex):
        a, b, c, d, e, f = models = list(models_complex)

        t = Transaction(strategy=PersistencyStrategy.INTERRUPT_ON_ERROR)
        t.register_dao(ModelDAOException(ModelA))

        f._state = ModelState.NEW
        e._state = ModelState.NEW
        d._state = ModelState.DIRTY
        b._state = ModelState.DELETED
        a._state = ModelState.DELETED
        a.ex = True

        for model in models:
            t.register_model(model)

        error_models, processed_models = await self._process_transaction(t)

        a_cache, b_cache = [t._model_cache.get_by_internal_id(ModelA, y._internal_id) for y in [a, b]]
        assert b_cache is None
        assert a_cache is not None
        assert a_cache._state == ModelState.DELETED

        assert set(processed_models) == set([f, e, d, b])
        assert len(error_models) == 1
        assert error_models.pop() == a

    async def _process_transaction(self, transaction):
        error_models = set()
        processed_models = set()

        for dao_task in await transaction.commit():
            try:
                await dao_task
                processed_models.add(dao_task.model)
            except Exception:
                error_models.add(dao_task.model)

        return error_models, processed_models

    @pytest.mark.asyncio
    async def _check_exception_strategies(self, models, strategy, expected):
        t = Transaction(strategy=strategy)
        t.register_dao(ModelDAOException(ModelA))

        for model in models:
            t.register_model(model)

        error_models, processed_models = await self._process_transaction(t)

        expected_processed, maybe_processed, expected_errors, expected_not_processed = expected
        pending_models = t.get_transaction_models()

        # A model that may have been processed is either processed or
        # pending. Intersecting both processed and pending lists should
        # then cover them all
        expected_processed_or_pending = maybe_processed.intersection(processed_models).union(
            maybe_processed.intersection(pending_models)
        )

        assert expected_processed.intersection(processed_models) == expected_processed
        assert maybe_processed == expected_processed_or_pending
        assert expected_errors == error_models
        assert expected_not_processed == (pending_models - maybe_processed)

    @pytest.mark.asyncio
    async def test_commit_exception_interrupt_on_error(self, models_strategy):
        a, b, c, d, e, f, g, h, i, j = models = models_strategy

        processed_when_canceled = set([b, f, g, h])
        maybe_processed_when_canceled = set([a, e])
        errors_when_canceled = set([d])
        not_processed_when_canceled = set([c, d, i, j])
        expected_canceled = (processed_when_canceled, maybe_processed_when_canceled,
                             errors_when_canceled, not_processed_when_canceled)

        await self._check_exception_strategies(models, PersistencyStrategy.INTERRUPT_ON_ERROR, expected_canceled)

    @pytest.mark.asyncio
    async def test_commit_exception_continue_on_error(self, models_strategy):
        a, b, c, d, e, f, g, h, i, j = models = models_strategy

        processed_when_ignored = set(models).difference(set([d]))
        maybe_processed_when_ignored = set()
        errors_when_ignored = set([d])
        not_processed_when_ignored = errors_when_ignored
        expected_ignored = (processed_when_ignored, maybe_processed_when_ignored,
                            errors_when_ignored, not_processed_when_ignored)

        await self._check_exception_strategies(models, PersistencyStrategy.CONTINUE_ON_ERROR, expected_ignored)

    @pytest.mark.asyncio
    async def test_process_all_trees(self, t, models_complex):
        models = set(models_complex)
        t.register_dao(ModelDAO(ModelA))

        for model in models:
            model._state = ModelState.NEW

        y = DependencyGraph.generate_from_objects(models)

        processed_models = set()
        async for dao_task in t._process_all_trees(y, NavigationDirection.LEAVES_TO_ROOTS):
            assert isinstance(dao_task, DAOTask)
            processed_models.add(dao_task.model)

        assert not models.difference(processed_models)

    @pytest.mark.asyncio
    async def test_process_tree(self, t, models):
        a, b, c = models
        t.register_dao(ModelDAO(ModelA))

        models = list([a, b, c])
        for model in models:
            model._state = ModelState.NEW

        y = DependencyGraph.generate_from_objects(models)

        processed_models = set()
        async for dao_task in t._process_tree(y.trees[0], NavigationDirection.LEAVES_TO_ROOTS):
            assert isinstance(dao_task, DAOTask)
            processed_models.add(dao_task.model)

        assert set(models) == processed_models

    @pytest.mark.asyncio
    async def test_get_dao_tasks(self, t, models):
        a, b, c = models
        t.register_dao(ModelDAO(ModelA))

        models = set([a, b, c])
        y = DependencyGraph.generate_from_objects(models)
        tree = y.trees[0]

        for state in (ModelState.NEW, ModelState.DIRTY, ModelState.DELETED):
            for model in models:
                model._state = state

            for node, dao_task in t._get_dao_tasks(tree.get_nodes()).items():
                node_return = dao_task.node
                model_return = await dao_task

                assert model_return == node.node_object
                assert dao_task.model == node.node_object
                assert node_return == node

    @pytest.mark.asyncio
    async def test_rollback(self, t, models_complex):
        a, b, c, d, e, f = models = list(models_complex)

        t.register_model(a)
        t.register_model(d)
        t.register_model(f)
        t.add(b)
        t.add(c)
        t.add(e)
        t.remove(f)

        d.v = 444

        a_cache, b_cache, c_cache, d_cache, e_cache, f_cache = \
            [await t.get(m.__class__, m.get_keys()) for m in models]

        assert a_cache._state == ModelState.CLEAN
        assert b_cache._state == ModelState.NEW
        assert c_cache._state == ModelState.NEW
        assert d_cache._state == ModelState.DIRTY
        assert e_cache._state == ModelState.NEW
        assert f_cache._state == ModelState.DELETED

        assert d_cache == d
        assert d_cache.v == 444

        t.rollback()

        a_cache = await t.get(a.__class__, a.get_keys())
        d_cache = await t.get(d.__class__, d.get_keys())

        for m in [b, c, e, f]:
            with pytest.raises(RuntimeError):
                await t.get(m.__class__, m.get_keys())

        assert a_cache._state == ModelState.CLEAN
        assert d_cache._state == ModelState.CLEAN

        assert a_cache == a
        assert d_cache == d
        assert d_cache.v == 44
