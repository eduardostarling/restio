from __future__ import annotations

import asyncio
import itertools
from random import randint
from typing import Iterable, List, Optional, Tuple, Type

import pytest

from restio.dao import BaseDAO, DAOTask
from restio.fields import (
    BoolField,
    FrozenSetField,
    FrozenSetModelField,
    IntField,
    ModelField,
    StrField,
    TupleField,
    TupleModelField,
)
from restio.fields.base import FrozenType
from restio.graph import DependencyGraph, NavigationType
from restio.model import MODEL_PRE_UPDATE_EVENT, MODEL_UPDATE_EVENT, BaseModel
from restio.query import query
from restio.state import ModelState
from restio.transaction import PersistencyStrategy, Transaction


class ModelA(BaseModel):
    key: IntField = IntField(pk=True)
    v: IntField = IntField()
    s: StrField = StrField()
    ex: BoolField = BoolField()
    ref: ModelField[BaseModel] = ModelField(BaseModel)

    def __init__(self, key=1, v=0, s="", ex=False, ref=None):
        self.key = key
        self.v = v
        self.s = s
        self.ex = ex
        self.ref = ref


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


class ModelFrozenDAO(BaseDAO):
    def __init__(self, model_type: Type[BaseModel], value):
        super().__init__(model_type)
        self.value = value

    def _register_children(self):
        if isinstance(self.value, Iterable):
            for v in self.value:
                if not isinstance(v, BaseModel):
                    continue
                self.transaction.register_model(v)
        elif isinstance(self.value, BaseModel):
            self.transaction.register_model(self.value)

    async def _method(self, obj: BaseModel):
        obj.field = self.value  # type: ignore
        self._register_children()

    async def get(self, *, key: int):
        obj = self._model_type()
        obj.key = key  # type: ignore
        await self._method(obj)
        return obj

    add = _method
    update = _method
    remove = _method


@query
async def SimpleQuery(
    query_arg: TestTransaction, a: ModelA, *, transaction
) -> Tuple[ModelA, ...]:
    b = ModelA(key=2, v=22, ref=a)
    c = ModelA(key=3, v=33, ref=b)

    assert isinstance(query_arg, TestTransaction)
    assert isinstance(transaction, Transaction)

    return a, b, c


@query
async def SimpleQueryRegister(
    register: bool = False, a: Optional[ModelA] = None, *, transaction: Transaction
) -> Tuple[ModelA, ...]:

    if not a:
        a = ModelA(key=1, v=11)
    b = ModelA(key=2, v=22, ref=a)
    c = ModelA(key=3, v=33, ref=b)

    if register:
        transaction.register_model(a)
        transaction.register_model(b)

    return (c,)


@query
async def SingleResultQuery(*, transaction: Transaction) -> Tuple[ModelA]:
    return (ModelA(key=1),)


@query
async def EmptyQuery(query_arg: TestTransaction, *, transaction) -> Tuple[ModelA, ...]:
    assert isinstance(query_arg, TestTransaction)
    assert isinstance(transaction, Transaction)

    return tuple()


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

        models = (a, b, c, d, e, f, g, h, i, j)

        for model in models[0:6]:
            model._state = ModelState.DIRTY

        # To add
        g._state = ModelState.NEW
        h._state = ModelState.NEW

        # To remove
        i._state = ModelState.DELETED
        j._state = ModelState.DELETED

        return models


def _get_all_frozen_fields_non_default(
    frozen: FrozenType, with_values: bool = True
) -> List:
    values = [1, "a", True, (1,), frozenset({"a"}), (ModelA(),), frozenset({ModelA()})]
    fields = [
        IntField(frozen=frozen),
        StrField(frozen=frozen),
        BoolField(frozen=frozen),
        TupleField(int, frozen=frozen),
        FrozenSetField(str, frozen=frozen),
        TupleModelField(ModelA, frozen=frozen),
        FrozenSetModelField(ModelA, frozen=frozen),
    ]

    if with_values:
        return list(zip(fields, values))
    else:
        return fields


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

        assert len(t._model_cache._id_cache.values()) == 2
        assert len(t._model_cache._key_cache.values()) == 2
        assert await t.get(ModelA, key=1) == a
        assert await t.get(ModelA, key=2) == b

    @pytest.mark.asyncio
    async def test_register_discarded_model(self, t):
        a = ModelA(key=1, v=11)
        a._state = ModelState.DISCARDED

        with pytest.raises(RuntimeError):
            t.register_model(a)

    @pytest.mark.asyncio
    async def test_unregister_model(self, t):
        a = ModelA(key=1, v=11)

        t.register_model(a)

        assert await t.get(ModelA, key=1) == a
        assert a._listener._listener[MODEL_PRE_UPDATE_EVENT]
        assert a._listener._listener[MODEL_UPDATE_EVENT]

        t.unregister_model(a)

        assert not a._listener._listener[MODEL_PRE_UPDATE_EVENT]
        assert not a._listener._listener[MODEL_UPDATE_EVENT]

    @pytest.mark.asyncio
    async def test_reset_cache_after_registering_models(self, t):
        a = ModelA(key=1, v=11)
        b = ModelA(key=2, v=22)

        assert MODEL_PRE_UPDATE_EVENT not in a._listener._listener
        assert MODEL_UPDATE_EVENT not in a._listener._listener
        assert MODEL_PRE_UPDATE_EVENT not in b._listener._listener
        assert MODEL_UPDATE_EVENT not in b._listener._listener

        t.register_model(a)
        t.register_model(b)

        assert len(t._model_cache._id_cache.values()) == 2
        assert len(t._model_cache._key_cache.values()) == 2
        assert await t.get(ModelA, key=1) == a
        assert await t.get(ModelA, key=2) == b
        assert a._listener._listener[MODEL_PRE_UPDATE_EVENT]
        assert a._listener._listener[MODEL_UPDATE_EVENT]
        assert b._listener._listener[MODEL_PRE_UPDATE_EVENT]
        assert b._listener._listener[MODEL_UPDATE_EVENT]

        t.reset()

        assert a._state == ModelState.DISCARDED
        assert b._state == ModelState.DISCARDED
        assert not a._listener._listener[MODEL_PRE_UPDATE_EVENT]
        assert not a._listener._listener[MODEL_UPDATE_EVENT]
        assert not b._listener._listener[MODEL_PRE_UPDATE_EVENT]
        assert not b._listener._listener[MODEL_UPDATE_EVENT]

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

        assert await t.get(ModelA, key=1) == old_a
        assert await t.get(ModelA, key=2) == old_b
        assert await t.get(ModelA, key=1) != a
        assert await t.get(ModelA, key=2) != b

        t.register_model(a, True)
        t.register_model(b, True)

        assert await t.get(ModelA, key=1) != old_a
        assert await t.get(ModelA, key=2) != old_b
        assert await t.get(ModelA, key=1) == a
        assert await t.get(ModelA, key=2) == b

    @pytest.mark.asyncio
    async def test_register_model_and_children(self, t, models):
        a, b, c = models
        for model in models:
            t.register_model(model)

        assert await t.get(ModelA, key=1) == a
        assert await t.get(ModelA, key=2) == b
        assert await t.get(ModelA, key=3) == c

    @pytest.mark.asyncio
    async def test_register_model_with_missing_children(self, t, models):
        _, b, c = models

        with pytest.raises(RuntimeError):
            t.register_model(c)

        with pytest.raises(RuntimeError):
            t.register_model(b)

    @pytest.mark.asyncio
    async def test_force_register_model_and_children(self, t, models):
        old_a, old_b, old_c = models
        new_c = ModelA(key=3)

        for model in models + (new_c,):
            t.register_model(model)

        assert await t.get(ModelA, key=1) == old_a
        assert await t.get(ModelA, key=2) == old_b
        assert await t.get(ModelA, key=3) == old_c
        assert await t.get(ModelA, key=3) != new_c

        t.register_model(new_c, force=True)

        assert await t.get(ModelA, key=1) == old_a
        assert await t.get(ModelA, key=2) == old_b
        assert await t.get(ModelA, key=3) != old_c
        assert await t.get(ModelA, key=3) == new_c

    @pytest.mark.asyncio
    async def test_get_model_registered_directly_in_cache(self, t, models):
        a, b, c = models

        t._model_cache.register(a)
        t._model_cache.register(b)
        t._model_cache.register(c)

        assert await t.get(ModelA, key=1) == a
        assert await t.get(ModelA, key=2) == b
        assert await t.get(ModelA, key=3) == c

    @pytest.mark.asyncio
    async def test_get_model_from_dao_after_cache_reset(self, t, models):
        a, _, _ = models

        t.register_model(a)
        assert await t.get(ModelA, key=1) == a

        t.reset()

        assert a._state == ModelState.DISCARDED
        assert t._model_cache._id_cache == {}
        assert t._model_cache._key_cache == {}
        assert t._query_cache._cache == {}

        # after reset, the transaction must try to call
        # the DAO since "a" has been cleared
        with pytest.raises(NotImplementedError):
            await t.get(ModelA, key=1)

    @pytest.mark.parametrize(
        "field_type, value", _get_all_frozen_fields_non_default(FrozenType.ALWAYS),
    )
    def test_set_field_frozen_always(self, t, field_type, value):
        class Model(BaseModel):
            field = field_type

        obj = Model()

        t.register_model(obj)

        with pytest.raises(ValueError, match="is frozen"):
            obj.field = value

    @pytest.mark.parametrize(
        "field_type, value", _get_all_frozen_fields_non_default(FrozenType.UPDATE),
    )
    def test_set_field_frozen_update(self, t, field_type, value):
        class Model(BaseModel):
            field = field_type

        obj = Model()

        t.register_model(obj)

        with pytest.raises(ValueError, match="is frozen"):
            obj.field = value

    @pytest.mark.parametrize(
        "field_type, value", _get_all_frozen_fields_non_default(FrozenType.CREATE),
    )
    def test_set_field_frozen_create(self, t, field_type, value):
        class Model(BaseModel):
            field = field_type

        obj = Model()
        t.register_dao(ModelDAO(Model))

        t.add(obj)

        with pytest.raises(ValueError, match="is frozen"):
            obj.field = value

    @pytest.mark.parametrize(
        "field_type, value", _get_all_frozen_fields_non_default(FrozenType.CREATE),
    )
    def test_set_field_frozen_add_different_from_default(self, t, field_type, value):
        class Model(BaseModel):
            field = field_type

        obj = Model()
        t.register_dao(ModelDAO(Model))

        obj.field = value

        with pytest.raises(ValueError, match="is frozen and its value"):
            t.add(obj)

        assert obj._state == ModelState.UNBOUND

    @pytest.mark.parametrize("set_default", [False, True])
    @pytest.mark.parametrize(
        "field_type",
        _get_all_frozen_fields_non_default(FrozenType.CREATE, with_values=False),
    )
    def test_set_field_frozen_add_default_values(self, t, field_type, set_default):
        class Model(BaseModel):
            field = field_type

        obj = Model()
        t.register_dao(ModelDAO(Model))

        if set_default:
            obj.field = field_type.default

        t.add(obj)

        assert obj._state == ModelState.NEW

    @pytest.mark.parametrize("method", ["get", "add", "update", "remove"])
    @pytest.mark.parametrize(
        "field_type, value", _get_all_frozen_fields_non_default(FrozenType.ALWAYS),
    )
    @pytest.mark.asyncio
    async def test_set_field_frozen_always_during_dao_method(
        self, t, field_type, value, method
    ):
        class Model(BaseModel):
            key = IntField(pk=True, allow_none=True)
            field = field_type
            aux = StrField()

            def __init__(self, key: Optional[int] = None):
                self.key = key

        t.register_dao(ModelFrozenDAO(Model, value))
        model = None

        if method == "get":
            model = await t.get(Model, key=1)  # trigger get on spot
            assert model.key == 1
        elif method == "add":
            model = Model(key=1)
            t.add(model)  # trigger add during commit
        elif method == "update":
            model = Model(key=1)
            t.register_model(model)
            model.aux = "a"  # trigger update during commit
        elif method == "remove":
            model = Model(key=1)
            t.register_model(model)
            t.remove(model)  # trigger remove during commit

        await t.commit()
        if model:
            assert model.field == value

    @pytest.mark.asyncio
    async def test_dao_check_add_not_implemented(self, t, models):
        a, *_ = models

        with pytest.raises(NotImplementedError, match="DAO"):
            t.add(a)

    @pytest.mark.asyncio
    async def test_dao_check_remove_not_implemented(self, t, models):
        a, *_ = models

        t.register_model(a)
        with pytest.raises(NotImplementedError, match="DAO"):
            t.remove(a)

    @pytest.mark.asyncio
    async def test_dao_check_update_not_implemented(self, t, models):
        a, *_ = models

        t.register_model(a)
        with pytest.raises(NotImplementedError, match="DAO"):
            a.v = 200

    @pytest.mark.asyncio
    async def test_get_new_model(self, t, models):
        a, b, c = models

        class ModelADAO(BaseDAO):
            async def get(self, *, key: int):
                assert self.transaction is not None

                if key == 1:
                    return a
                elif key == 2:
                    return b
                elif key == 3:
                    return c

                return None

        t.register_dao(ModelADAO(ModelA))

        assert await t.get(ModelA, key=1) == a
        assert a._state == ModelState.CLEAN
        assert await t.get(ModelA, key=2) == b
        assert b._state == ModelState.CLEAN
        assert await t.get(ModelA, key=3) == c
        assert c._state == ModelState.CLEAN

        with pytest.raises(RuntimeError):
            assert await t.get(ModelA, key=4) is None

    @pytest.mark.asyncio
    async def test_get_new_model_concurrent(self, t):
        class ModelDAO(BaseDAO):
            a = None

            async def get(self, *, key: int):
                await asyncio.sleep(randint(1, 2) / 10000)
                model = ModelA(key=key)
                if not ModelDAO.a:
                    ModelDAO.a = model
                return model

        t.register_dao(ModelDAO(ModelA))

        tasks = [t.get(ModelA, key=1) for _ in range(5)]
        for task in asyncio.as_completed(tasks):
            result = await task
            assert result._internal_id == ModelDAO.a._internal_id

    @pytest.mark.asyncio
    async def test_get_new_model_without_registered_dao(self, t):
        with pytest.raises(RuntimeError):
            await t.get(ModelA, key=1)

    @pytest.mark.asyncio
    async def test_get_new_model_with_dao_get_not_implemented(self, t):
        t.register_dao(BaseDAO(BaseModel))
        with pytest.raises(RuntimeError):
            await t.get(BaseModel, key=1)

    @pytest.mark.asyncio
    async def test_query_with_empty_cache(self, t):
        a_input = ModelA(v=11)

        q = SimpleQuery(query_arg=self, a=a_input)

        # performs query
        a, b, c = await t.query(q)

        assert await t.get(ModelA, key=1) == a
        assert await t.get(ModelA, key=2) == b
        assert await t.get(ModelA, key=3) == c
        assert a == a_input

    @pytest.mark.asyncio
    async def test_query_that_doesnt_self_register_models(self, t, models):
        q = SimpleQueryRegister(register=False)

        with pytest.raises(RuntimeError):
            await t.query(q)

    @pytest.mark.asyncio
    async def test_query_that_self_registers_models(self, t, models):
        q = SimpleQueryRegister(register=True)
        q_result = await t.query(q)

        assert q_result

    @pytest.mark.asyncio
    async def test_query_with_existing_model_in_cache_and_different_result(
        self, t, models
    ):
        a, *_ = models

        t.register_model(a)

        q = SingleResultQuery()
        q_result = await t.query(q)

        assert a in q_result

    @pytest.mark.asyncio
    async def test_query_with_existing_model_in_cache_and_dependencies(self, t, models):
        a, *_ = models

        t.register_model(a)

        q = SimpleQueryRegister(register=True, a=a)
        q_result = await t.query(q)

        assert q_result
        assert q_result[0].ref.ref == a  # c -> b -> a

    @pytest.mark.asyncio
    async def test_query_with_existing_model_in_cache_and_dependencies_and_different_result(
        self, t, models
    ):
        a, *_ = models

        t.register_model(a)

        q = SimpleQueryRegister(register=True)

        # fails because the ModelA(key=1) returned by the query
        # contains children that are not registered yet, and since
        # there was already a ModelA(key=1) in the cache, the parent
        # can't be registered
        with pytest.raises(RuntimeError):
            await t.query(q)

    @pytest.mark.asyncio
    async def test_empty_query_results(self, t):
        q = EmptyQuery(self)
        assert await t.query(q) == tuple()

    def test_assert_cache_internal_id(self, t):
        with pytest.raises(RuntimeError):
            t._assert_cache_internal_id(ModelA())

    @pytest.mark.asyncio
    async def test_add_model(self, t, models):
        a, _, _ = models
        t.register_dao(ModelDAO(ModelA))

        t.add(a)

        cached_a = await t.get(ModelA, key=1)

        assert cached_a == a
        assert cached_a._state == ModelState.NEW

    @pytest.mark.asyncio
    async def test_add_model_twice(self, t, models):
        a, _, _ = models
        t.register_dao(ModelDAO(ModelA))

        t.add(a)
        with pytest.raises(RuntimeError, match="is already registered"):
            t.add(a)

    @pytest.mark.asyncio
    async def test_add_discarded_model(self, t, models):
        a, _, _ = models
        t.register_dao(ModelDAO(ModelA))

        a._state = ModelState.DISCARDED

        with pytest.raises(RuntimeError, match="has been discarded"):
            t.add(a)

    @pytest.mark.asyncio
    async def test_update_model(self, t, models):
        a, _, _ = models
        t.register_dao(ModelDAO(ModelA))

        old_a_value = a.v

        t.register_model(a)
        cached_a = await t.get(ModelA, key=1)

        assert cached_a == a
        assert cached_a._state == ModelState.CLEAN

        a.v = 100
        cached_a = await t.get(ModelA, key=1)

        assert cached_a._state == ModelState.DIRTY
        assert cached_a.v == 100
        assert cached_a._persistent_values == {"v": old_a_value}

    @pytest.mark.asyncio
    async def test_update_twice(self, t, models):
        a, _, _ = models
        t.register_dao(ModelDAO(ModelA))

        old_a_value = a.v
        old_a_string = a.s

        t.register_model(a)

        a.v = 100
        a.v = old_a_value
        a.s = "string"

        cached_a = await t.get(ModelA, key=1)

        assert cached_a._state == ModelState.DIRTY
        assert cached_a.v == old_a_value
        assert cached_a.s == "string"
        assert cached_a._persistent_values == {"s": old_a_string}

    @pytest.mark.asyncio
    async def test_update_to_persistent(self, t, models):
        a, _, _ = models
        t.register_dao(ModelDAO(ModelA))

        old_a_value = a.v
        old_a_string = a.s

        t.register_model(a)

        a.v = 100
        a.s = "string"
        a.v = old_a_value
        a.s = old_a_string

        cached_a = await t.get(ModelA, key=1)

        assert cached_a._state == ModelState.CLEAN
        assert cached_a.v == old_a_value
        assert cached_a.s == old_a_string
        assert cached_a._persistent_values == {}

    @pytest.mark.asyncio
    async def test_update_new(self, t, models):
        a, _, _ = models
        t.register_dao(ModelDAO(ModelA))

        t.add(a)
        cached_a = await t.get(ModelA, key=1)

        assert cached_a == a
        assert cached_a._state == ModelState.NEW

        a.v = 100
        cached_a = await t.get(ModelA, key=1)

        assert cached_a._state == ModelState.NEW
        assert cached_a.v == 100
        assert cached_a._persistent_values == {}

    @pytest.mark.asyncio
    async def test_commit_new_primary_key(self, t, models):
        a, _, _ = models
        old_key = a.key

        class ModelADAO(BaseDAO):
            async def get(self, *, key: int):
                if key == old_key:
                    return None
                else:
                    raise ValueError(
                        "Request using the new key did not return from cache."
                    )

            async def update(self, obj):
                pass

        t.register_dao(ModelADAO(ModelA))
        t.register_model(a)

        a.key = 11
        # try getting the model by its old key
        cached_a = await t.get(ModelA, key=old_key)
        assert cached_a == a

        # the commit should always remap the primary keys
        await t.commit()

        # this should fail, as nothing was returned
        with pytest.raises(RuntimeError):
            await t.get(ModelA, key=old_key)

        # this should return the model from the cache
        correct_cached_a = await t.get(ModelA, key=a.key)
        assert correct_cached_a == a

    @pytest.mark.asyncio
    async def test_remove(self, t, models):
        a, _, _ = models
        t.register_dao(ModelDAO(ModelA))

        t.register_model(a)
        cached_a = await t.get(ModelA, key=1)

        assert cached_a == a
        assert cached_a._state == ModelState.CLEAN

        t.remove(a)

        cached_a = await t.get(ModelA, key=1)

        assert cached_a._state == ModelState.DELETED

    def test_check_deleted_models(self, models):
        a, b, c = models
        a._state = ModelState.DELETED
        b._state = ModelState.DELETED

        with pytest.raises(RuntimeError):
            Transaction._check_deleted_models(models)

        c._state = ModelState.DELETED
        Transaction._check_deleted_models(models)

    commit_iterations = itertools.product(
        [ModelState.NEW, ModelState.DIRTY, ModelState.CLEAN], repeat=6
    )

    @pytest.mark.parametrize("states", commit_iterations)
    @pytest.mark.asyncio
    async def test_commit(self, t, models_complex, states):
        t.register_dao(ModelDAO(ModelA))

        for index, model in enumerate(models_complex):
            model._state = states[index]

        for model in models_complex:
            t.register_model(model)

        await t.commit()

        models_in_cache = t._model_cache.get_all_models()

        for model in models_in_cache:
            assert model._state == ModelState.CLEAN
            assert model._persistent_values == {}

    commit_with_deleted_iterations = itertools.product(
        [ModelState.NEW, ModelState.DIRTY, ModelState.CLEAN], repeat=3
    )

    @pytest.mark.parametrize("states", commit_with_deleted_iterations)
    @pytest.mark.parametrize("tree_models", ("abc", "def"))
    @pytest.mark.asyncio
    async def test_commit_with_delete(self, t, models_complex, tree_models, states):
        a, b, c, d, e, f = models_complex
        models_modified = {a, b, c} if tree_models == "abc" else {d, e, f}
        models_deleted = set(models_complex) - models_modified

        t.register_dao(ModelDAO(ModelA))

        for index, model in enumerate(models_modified):
            model._state = states[index]

        for model in models_deleted:
            model._state = ModelState.DELETED

        for model in models_complex:
            t.register_model(model)

        await t.commit()

        models_in_cache = t._model_cache.get_all_models()

        for model in models_in_cache:
            assert model._state == ModelState.CLEAN
            assert model._persistent_values == {}

        assert len(set(models_in_cache).intersection(models_deleted)) == 0

    @pytest.mark.asyncio
    async def test_commit_exception(self, models_complex):
        a, b, c, d, e, f = models = list(models_complex)

        t = Transaction(strategy=PersistencyStrategy.INTERRUPT_ON_ERROR)
        t.register_dao(ModelDAOException(ModelA))

        f._state = ModelState.NEW
        e._state = ModelState.NEW
        d._state = ModelState.DIRTY
        c._state = ModelState.DELETED
        b._state = ModelState.DELETED
        a._state = ModelState.DELETED
        b.ex = True

        for model in models:
            t.register_model(model)

        (
            error_models,
            processed_models,
            not_processed_models,
        ) = await self._process_transaction(t)

        a_cache, b_cache, c_cache = [
            t._model_cache.get_by_internal_id(ModelA, y._internal_id) for y in (a, b, c)
        ]
        assert c_cache is None
        assert b_cache is not None
        assert a_cache is not None
        assert b_cache._state == ModelState.DELETED
        assert a_cache._state == ModelState.DELETED

        assert processed_models == {f, e, d, c}
        assert error_models == {b}
        assert not_processed_models == {a}

    async def _process_transaction(self, transaction: Transaction):
        error_models = set()
        processed_models = set()
        all_models = transaction._model_cache.get_all_models()

        for dao_task in await transaction.commit():
            try:
                await dao_task
                processed_models.add(dao_task.model)
            except Exception:
                error_models.add(dao_task.model)

        not_processed_models = all_models - error_models - processed_models
        return error_models, processed_models, not_processed_models

    @pytest.mark.asyncio
    async def _check_exception_strategies(self, models, strategy, expected):
        t = Transaction(strategy=strategy)
        t.register_dao(ModelDAOException(ModelA))

        for model in reversed(models):
            t.register_model(model)

        error_models, processed_models, _ = await self._process_transaction(t)

        (
            expected_processed,
            maybe_processed,
            expected_errors,
            expected_not_processed,
        ) = expected
        pending_models = t._get_models_by_state(
            (ModelState.NEW, ModelState.DIRTY, ModelState.DELETED)
        )

        # A model that may have been processed is either processed or
        # pending. Intersecting both processed and pending lists should
        # then cover them all
        expected_processed_or_pending = maybe_processed.intersection(
            processed_models
        ).union(maybe_processed.intersection(pending_models))

        assert expected_processed.intersection(processed_models) == expected_processed
        assert maybe_processed == expected_processed_or_pending
        assert expected_errors == error_models
        assert expected_not_processed == (pending_models - maybe_processed)

    @pytest.mark.asyncio
    async def test_commit_exception_interrupt_on_error(self, models_strategy):
        a, b, c, d, e, f, g, h, i, j = models = models_strategy

        processed_when_canceled = {b, f, g, h}
        maybe_processed_when_canceled = {a, e}
        errors_when_canceled = {d}
        not_processed_when_canceled = {c, d, i, j}
        expected_canceled = (
            processed_when_canceled,
            maybe_processed_when_canceled,
            errors_when_canceled,
            not_processed_when_canceled,
        )

        await self._check_exception_strategies(
            models, PersistencyStrategy.INTERRUPT_ON_ERROR, expected_canceled
        )

    @pytest.mark.asyncio
    async def test_commit_exception_continue_on_error(self, models_strategy):
        a, b, c, d, e, f, g, h, i, j = models = models_strategy

        processed_when_ignored = set(models).difference({d})
        maybe_processed_when_ignored = set()
        errors_when_ignored = {d}
        not_processed_when_ignored = errors_when_ignored
        expected_ignored = (
            processed_when_ignored,
            maybe_processed_when_ignored,
            errors_when_ignored,
            not_processed_when_ignored,
        )

        await self._check_exception_strategies(
            models, PersistencyStrategy.CONTINUE_ON_ERROR, expected_ignored
        )

    @pytest.mark.asyncio
    async def test_process_all_trees(self, t, models_complex):
        models = set(models_complex)
        t.register_dao(ModelDAO(ModelA))

        for model in models_complex:
            model._state = ModelState.NEW

        y = DependencyGraph.generate_from_objects(models)

        processed_models = set()
        async for dao_task in t._process_all_trees(y, NavigationType.LEAVES_TO_ROOTS):
            assert isinstance(dao_task, DAOTask)
            processed_models.add(dao_task.model)

        assert not models.difference(processed_models)

    @pytest.mark.asyncio
    async def test_process_tree(self, t, models):
        a, b, c = models
        t.register_dao(ModelDAO(ModelA))

        models = [a, b, c]
        for model in models:
            model._state = ModelState.NEW

        y = DependencyGraph.generate_from_objects(models)

        processed_models = set()
        async for dao_task in t._process_tree(
            y.trees[0], NavigationType.LEAVES_TO_ROOTS
        ):
            assert isinstance(dao_task, DAOTask)
            processed_models.add(dao_task.model)

        assert set(models) == processed_models

    @pytest.mark.asyncio
    async def test_get_dao_tasks(self, t, models):
        a, b, c = models
        t.register_dao(ModelDAO(ModelA))

        models = {a, b, c}
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
        t.register_dao(ModelDAO(ModelA))

        t.register_model(a)
        t.add(b)
        t.add(c)
        t.register_model(d)
        t.register_model(f)
        t.add(e)
        t.remove(f)

        d.v = 444

        a_cache, b_cache, c_cache, d_cache, e_cache, f_cache = [
            await t.get(m.__class__, **m.primary_keys) for m in models
        ]

        assert a_cache._state == ModelState.CLEAN
        assert b_cache._state == ModelState.NEW
        assert c_cache._state == ModelState.NEW
        assert d_cache._state == ModelState.DIRTY
        assert e_cache._state == ModelState.NEW
        assert f_cache._state == ModelState.DELETED

        assert d_cache == d
        assert d_cache.v == 444

        t.rollback()

        a_cache = await t.get(a.__class__, **a.primary_keys)
        d_cache = await t.get(d.__class__, **d.primary_keys)

        for m in [b, c, e, f]:
            with pytest.raises(RuntimeError):
                await t.get(m.__class__, **m.primary_keys)

        assert a_cache._state == ModelState.CLEAN
        assert d_cache._state == ModelState.CLEAN

        assert a_cache == a
        assert d_cache == d
        assert d_cache.v == 44
