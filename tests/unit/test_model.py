from __future__ import annotations

from uuid import UUID

import pytest

from restio.event import EventListener
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
from restio.model import MODEL_UPDATE_EVENT, BaseModel


class ModelSinglePKInt(BaseModel):
    id: IntField = IntField(pk=True)


class ModelSinglePKStr(BaseModel):
    id: StrField = StrField(pk=True)


class ModelDoublePKIntStr(BaseModel):
    id: IntField = IntField(pk=True)
    key: StrField = StrField(pk=True)


class ModelDoublePKStrInt(BaseModel):
    key: StrField = StrField(pk=True)
    id: IntField = IntField(pk=True)


class TestModelPrimaryKeys:
    def test_primary_key_int(self):
        single_int = ModelSinglePKInt()
        single_int.id = 1

        assert single_int.id == 1
        assert single_int.primary_keys == dict(id=1)

    def test_primary_key_str(self):
        single_str = ModelSinglePKStr()
        single_str.id = "1"

        assert single_str.id == "1"
        assert single_str.primary_keys == dict(id="1")

    def test_primary_key_double_int_str(self):
        double_is = ModelDoublePKIntStr()
        double_is.id, double_is.key = 1, "2"

        assert double_is.id == 1
        assert double_is.key == "2"
        assert double_is.primary_keys == dict(id=1, key="2")

    def test_primary_key_double_str_int(self):
        double_si = ModelDoublePKStrInt()
        double_si.key, double_si.id = "1", 2

        assert double_si.key == "1"
        assert double_si.id == 2
        assert double_si.primary_keys == dict(key="1", id=2)

    def test_primary_key_set_error(self):
        single_int = ModelSinglePKInt()
        with pytest.raises(TypeError, match="should be of type"):
            single_int.id = "1"

        single_int.id = 2
        assert single_int.id == 2
        assert single_int.primary_keys == dict(id=2)

        single_int.id = 3
        assert single_int.id == 3
        assert single_int.primary_keys == dict(id=3)


class ModelA(BaseModel):
    id: IntField = IntField(pk=True)
    a: IntField = IntField()
    b: StrField = StrField()
    c: TupleField = TupleField(str)
    d: FrozenSetField = FrozenSetField(int)
    e: BoolField = BoolField()


class ModelB(BaseModel):
    ref: ModelField[ModelA] = ModelField(ModelA)
    c: StrField = StrField()


class ModelC(BaseModel):
    ref_tuple: TupleModelField[ModelB] = TupleModelField(ModelB)
    ref_frozenset: FrozenSetModelField[ModelB] = FrozenSetModelField(ModelB)
    d: StrField = StrField()


class TestModel:
    def test_model_internal_uuid(self):
        class Model(BaseModel):
            pass

        model_a = Model()
        model_b = Model()

        assert model_a._internal_id
        assert model_b._internal_id
        assert isinstance(model_a._internal_id, UUID)
        assert isinstance(model_b._internal_id, UUID)
        assert model_a._internal_id != model_b._internal_id

    def test_model_persistent_values(self):
        class Model(BaseModel):
            pass

        model_a = Model()
        model_b = Model()

        assert model_a._persistent_values == {}
        assert model_b._persistent_values == {}
        assert id(model_a._persistent_values) != id(model_b._persistent_values)

    def test_model_initialized(self):
        class Model(BaseModel):
            def __init__(self):
                assert not self._initialized

        model = Model()

        assert model._initialized

    def test_model_event_listener(self):
        class Model(BaseModel):
            def __init__(self):
                assert not self._listener

        model = Model()

        assert model._listener
        assert isinstance(model._listener, EventListener)

    def test_model_equality(self):
        class Model(BaseModel):
            pass

        model_a, model_b = Model(), Model()

        assert model_a != model_b

        model_b._internal_id = model_a._internal_id

        assert model_a == model_b

    @pytest.mark.parametrize(
        "model, expected_fields, expected_dependency_fields",
        [
            (
                ModelA(),
                {"id": 0, "a": 0, "b": "", "c": tuple(), "d": frozenset(), "e": False},
                {},
            ),
            (ModelB(), {"ref": None, "c": ""}, {"ref": None}),
            (
                ModelC(),
                {"ref_tuple": tuple(), "ref_frozenset": frozenset(), "d": ""},
                {"ref_tuple": tuple(), "ref_frozenset": frozenset()},
            ),
        ],
    )
    def test_model_fields(self, model, expected_fields, expected_dependency_fields):
        assert model._meta.fields.keys() == expected_fields.keys()
        assert model.fields == expected_fields
        assert model.dependency_fields == expected_dependency_fields

    def test_model_fields_inheritance(self):
        class Model(BaseModel):
            a: IntField = IntField(default=1)
            non_field_a: int = 0

        class ChildModel(Model):
            b: StrField = StrField()
            non_field_b: str = ""

        model = Model()
        child_model = ChildModel()

        assert Model._meta.fields.keys() == {"a"}
        assert ChildModel._meta.fields.keys() == {"a", "b"}

        assert model.fields == {"a": 1}
        assert child_model.fields == {"a": 1, "b": ""}

    def test_model_update(self):
        model = ModelA()
        old_value = model.a
        field = model._meta.fields["a"]

        assert model._persistent_values == {}

        model._update(field, 55)
        assert model.is_field_modified("a")
        assert model._persistent_values == {"a": old_value}

        model._update(field, 66)
        assert model.is_field_modified("a")
        assert model._persistent_values == {"a": old_value}

        model._update(field, old_value)
        assert not model.is_field_modified("a")
        assert model._persistent_values == {}

    def test_change_field_value(self):
        a = ModelA()

        old_value_a, old_value_b = a.a, a.b
        new_value_a = 11
        new_value_b = "new value b"

        a.a = new_value_a
        assert a.a == new_value_a
        assert a.b == old_value_b
        assert a._persistent_values == {"a": old_value_a}

        a.b = new_value_b
        assert a.a == new_value_a
        assert a.b == new_value_b
        assert a._persistent_values == {"a": old_value_a, "b": old_value_b}

        a.a = old_value_a
        assert a.a == old_value_a
        assert a.b == new_value_b
        assert a._persistent_values == {"b": old_value_b}

        a.b = old_value_b
        assert a.a == old_value_a
        assert a.b == old_value_b
        assert not a._persistent_values

    def test_change_field_value_two_instances(self):
        model_a, model_b = ModelA(), ModelA()

        old_model_a_value = model_a.a
        old_model_b_value = model_b.a

        model_a.a = 55
        assert model_a._persistent_values == {"a": old_model_a_value}
        assert model_b._persistent_values == {}

        model_a.a = old_model_a_value
        model_b.a = 55
        assert model_a._persistent_values == {}
        assert model_b._persistent_values == {"a": old_model_b_value}

    def test_model_update_dispatch(self):
        called = False
        called_instance = None

        model = ModelA()

        def listen(instance):
            nonlocal called, called_instance
            called = True
            called_instance = instance

        model._listener.subscribe(MODEL_UPDATE_EVENT, listen)

        model.a = 2

        assert called
        assert id(called_instance) == id(model)

    def test_get_children(self):
        a, b1, b2, c = ModelA(), ModelB(), ModelB(), ModelC()

        c.ref_tuple, c.ref_frozenset, b1.ref, b2.ref = (b1,), frozenset({b2}), a, None

        all_children = c.get_children(True)
        assert a in all_children
        assert b1 in all_children
        assert b2 in all_children

        two_children = c.get_children(False)
        assert b1 in two_children
        assert b2 in two_children
        assert a not in two_children

    def test_get_children_circular(self):
        class ModelBCircular(ModelB):
            ref: ModelField[ModelC] = ModelField(ModelC)

        b, c = ModelBCircular(), ModelC()

        c.ref_frozenset, b.ref = frozenset({b}), c
        one_child = c.get_children(True)

        assert b in one_child
        assert c not in one_child
