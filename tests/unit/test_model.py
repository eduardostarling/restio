from __future__ import annotations

from typing import Any, Dict
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
from restio.model import MODEL_UPDATE_EVENT, BaseModel, ModelMeta


class ModelSinglePKInt(BaseModel):
    id: IntField = IntField(pk=True, allow_none=True)


class ModelSinglePKStr(BaseModel):
    id: StrField = StrField(pk=True, allow_none=True)


class ModelDoublePKIntStr(BaseModel):
    id: IntField = IntField(pk=True, allow_none=True)
    key: StrField = StrField(pk=True, allow_none=True)


class ModelDoublePKStrInt(BaseModel):
    key: StrField = StrField(pk=True, allow_none=True)
    id: IntField = IntField(pk=True, allow_none=True)


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
    id: IntField = IntField(default=0, pk=True)
    a: IntField = IntField(default=0)
    b: StrField = StrField(default="")
    c: TupleField = TupleField(str, default_factory=tuple)
    d: FrozenSetField = FrozenSetField(int, default_factory=frozenset)
    e: BoolField = BoolField(default=False)


class ModelB(BaseModel):
    ref: ModelField[ModelA] = ModelField(ModelA)
    c: StrField = StrField(default="")


class ModelC(BaseModel):
    ref_tuple: TupleModelField[ModelB] = TupleModelField(ModelB, default_factory=tuple)
    ref_frozenset: FrozenSetModelField[ModelB] = FrozenSetModelField(
        ModelB, default_factory=frozenset
    )
    d: StrField = StrField(default="")


default_model = ModelA()


class TestModel:
    def test_model_internal_uuid(self):
        class Model(BaseModel):
            def __init__(self):
                assert not self._internal_id

        model_a = Model()
        model_b = Model()

        assert model_a._internal_id
        assert model_b._internal_id
        assert isinstance(model_a._internal_id, UUID)
        assert isinstance(model_b._internal_id, UUID)
        assert model_a._internal_id != model_b._internal_id

    def test_model_hash(self):
        class Model(BaseModel):
            def __init__(self):
                assert not self._hash

        model_a = Model()

        assert model_a
        assert isinstance(model_a._hash, int)
        assert hash(model_a) == model_a._hash

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

        assert model_a != model_b

    def test_model_meta_defaults(self):
        class Model(BaseModel):
            class Meta:
                fields = {"a", "b"}
                primary_keys = {"a"}

        model = Model()

        assert model._meta.init
        assert model._meta.init_ignore_extra
        assert model._meta.fields == {}
        assert model._meta.primary_keys == {}

    def _assert_model_meta(self, model: BaseModel, meta_dict: Dict[str, Any]):
        meta = ModelMeta()

        for meta_attr in meta.__slots__:
            # assert child class
            if meta_attr in meta_dict:
                assert getattr(model._meta, meta_attr) == meta_dict[meta_attr]
            else:
                default = getattr(meta, meta_attr)
                assert getattr(model._meta, meta_attr) == default

    @pytest.mark.parametrize(
        "meta_field, value", [("init", False), ("init_ignore_extra", False)]
    )
    def test_model_meta_configurable(self, meta_field, value):
        meta_dict = {meta_field: value}

        class Model(BaseModel):
            Meta = type("Meta", (), meta_dict)

        model = Model()

        self._assert_model_meta(model, meta_dict)

    @pytest.mark.parametrize(
        "meta_field, value_parent, value_child",
        [("init", False, True), ("init_ignore_extra", False, True)],
    )
    def test_model_meta_configurable_inheritance_single_substitution(
        self, meta_field, value_parent, value_child
    ):
        meta_child_dict = {meta_field: value_child}
        meta_parent_dict = {meta_field: value_parent}

        class ParentModel(BaseModel):
            Meta = type("Meta", (), meta_parent_dict)

        class ChildModel(ParentModel):
            Meta = type("Meta", (), meta_child_dict)

        parent_model = ParentModel()
        child_model = ChildModel()

        self._assert_model_meta(parent_model, meta_parent_dict)
        self._assert_model_meta(child_model, meta_child_dict)

    def test_model_meta_configurable_inheritance_multiple_substitution(self):
        class ParentModel(BaseModel):
            class Meta:
                init = False

        class ChildModel(ParentModel):
            class Meta:
                init = True
                init_extra_ignore = False

        class GrandChildModel(ChildModel):
            class Meta:
                init = False
                init_extra_ignore = True

        parent_model = ParentModel()
        child_model = ChildModel()
        grand_child_model = GrandChildModel()

        self._assert_model_meta(parent_model, {"init": False})
        self._assert_model_meta(child_model, {"init": True, "init_extra_ignore": False})
        self._assert_model_meta(
            grand_child_model, {"init": False, "init_extra_ignore": True}
        )

    def test_all_field_types_in_model(self):
        class AllFieldsModel(BaseModel):
            int_key = IntField(pk=True)
            str_key = StrField(pk=True)
            int_field = IntField()
            str_field = StrField()
            bool_field = BoolField()
            tuple_field = TupleField(str)
            set_field = FrozenSetField(int)
            model_field = ModelField(ModelA)
            tuple_model_field = TupleModelField(ModelA)
            set_model_field = FrozenSetModelField(ModelA)
            non_field: str

        assert AllFieldsModel._meta.fields.keys() == {
            "int_key",
            "str_key",
            "int_field",
            "str_field",
            "bool_field",
            "tuple_field",
            "set_field",
            "model_field",
            "tuple_model_field",
            "set_model_field",
        }

    @pytest.mark.parametrize(
        "model, expected_fields, expected_dependency_fields",
        [
            (
                default_model,
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

    @pytest.mark.parametrize(
        "field_type, default",
        [
            (IntField, 1),
            (StrField, "a"),
            (BoolField, True),
            (lambda default: TupleField(int, default_factory=default), lambda: (1, 2)),
            (
                lambda default: FrozenSetField(str, default_factory=default),
                lambda: frozenset(["a", "b"]),
            ),
            (lambda default: ModelField(ModelA, default=default), default_model),
            (
                lambda default: TupleModelField(ModelA, default_factory=default),
                lambda: (default_model,),
            ),
            (
                lambda default: FrozenSetModelField(ModelA, default_factory=default),
                lambda: frozenset({default_model}),
            ),
        ],
    )
    def test_model_fields_custom_default(self, field_type, default):
        class Model(BaseModel):
            field = field_type(default=default)

        obj = Model()

        assert Model._meta.fields.keys() == {"field"}
        assert obj.field == default() if callable(default) else default

    def test_model_fields_inheritance(self):
        class Model(BaseModel):
            a: IntField = IntField(default=1)
            non_field_a: int = 0

        class ChildModel(Model):
            b: StrField = StrField(default="v")
            non_field_b: str = ""

        class GrandChildModel(ChildModel):
            b: IntField = IntField(default=2)

        model = Model()
        child_model = ChildModel()
        grand_child_model = GrandChildModel()

        assert Model._meta.fields.keys() == {"a"}
        assert ChildModel._meta.fields.keys() == {"a", "b"}
        assert GrandChildModel._meta.fields.keys() == {"a", "b"}

        assert model.fields == {"a": 1}
        assert child_model.fields == {"a": 1, "b": "v"}
        assert grand_child_model.fields == {"a": 1, "b": 2}

    def test_model_generated_constructor(self):
        class Model(BaseModel):
            a: IntField = IntField(default=1)
            b: StrField = StrField(default="default")

        model = Model()
        model_const = Model(a=2, b="default_const")

        assert model.a == 1
        assert model.b == "default"

        assert model_const.a == 2
        assert model_const.b == "default_const"

    def test_model_generated_constructor(self):
        class Model(BaseModel):
            a: IntField = IntField(default=1)
            b: StrField = StrField(default="default")

        model = Model()
        model_const = Model(a=2, b="default_const")
        model_part_const = Model(a=3, c="ignored")

        assert model.a == 1
        assert model.b == "default"

        assert model_const.a == 2
        assert model_const.b == "default_const"

        assert model_part_const.a == 3
        assert model_part_const.b == "default"

    def test_model_generated_constructor_partially_default(self):
        class Model(BaseModel):
            a: IntField = IntField(default=1)
            b: StrField = StrField()

        model = Model(b="value")

        assert model.a == 1
        assert model.b == "value"

    def test_model_non_generated_constructor(self):
        class Model(BaseModel):
            class Meta:
                init = False

            a: IntField = IntField(default=1)
            b: StrField = StrField(default="default")

        model = Model(a=2, b="default_const")

        assert model.a == 1
        assert model.b == "default"

    def test_model_generated_constructor_ignored_extras(self):
        class Model(BaseModel):
            a: IntField = IntField()
            b: StrField = StrField()

        Model(a=2, b="default_const", c="not_ignored")

    def test_model_generated_constructor_not_ignored_extras(self):
        class Model(BaseModel):
            class Meta:
                init_ignore_extra = False

            a: IntField = IntField()
            b: StrField = StrField()

        with pytest.raises(ValueError, match="Invalid argument"):
            Model(a=2, b="default_const", c="not_ignored")

    def test_model_generated_constructor_missing_values(self):
        class Model(BaseModel):
            a: IntField = IntField()
            b: StrField = StrField()

        with pytest.raises(ValueError, match="Can't initialize field"):
            Model()

        with pytest.raises(ValueError, match="Can't initialize field"):
            Model(a=2)

        with pytest.raises(ValueError, match="Can't initialize field"):
            Model(b="")

    def test_model_generated_constructor_partially_initialized(self):
        class Model(BaseModel):
            a: IntField = IntField()
            b: StrField = StrField(init=False, default="default")

        model = Model(a=1)
        model_part = Model(a=1, b="non-default")

        assert model.a == 1
        assert model.b == "default"

        assert model_part.a == 1
        assert model_part.b == "default"

    def test_model_generated_constructor_not_initialized_without_default(self):
        class Model(BaseModel):
            a: IntField = IntField()
            b: StrField = StrField(init=False)

        with pytest.raises(ValueError, match="Can't initialize field"):
            Model(a=1)

        with pytest.raises(ValueError, match="Can't initialize field"):
            Model(a=1, b="")

    def test_model_generated_constructor_ignored_extras_not_initialized(self):
        class Model(BaseModel):
            class Meta:
                init_ignore_extra = False

            a: IntField = IntField()
            b: StrField = StrField(init=False)

        with pytest.raises(ValueError, match="cannot be initialized"):
            Model(a=2, b="default_const")

    def test_model_manual_constructor_with_super_call(self):
        class Model(BaseModel):
            a: IntField = IntField()
            b: StrField = StrField()

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.a = self.a + 1

        model = Model(a=1, b="val")

        assert model.a == 2
        assert model.b == "val"

    def test_model_manual_constructor_without_super_call(self):
        class Model(BaseModel):
            a: IntField = IntField()
            b: StrField = StrField()

            def __init__(self, a: int, b: str):
                self.a = a + 1
                self.b = b + "-added"

        model = Model(a=1, b="val")

        assert model.a == 2
        assert model.b == "val-added"

    def test_model_update_persistent_values(self):
        model = ModelA()
        old_value_a = model.a
        old_value_b = model.b
        field_a = model._meta.fields["a"]
        field_b = model._meta.fields["b"]

        assert model._persistent_values == {}

        model._update_persistent_values(field_a, 55)
        assert model.is_field_modified("a")
        assert model._persistent_values == {"a": old_value_a}

        model._update_persistent_values(field_b, "b")
        assert model.is_field_modified("a")
        assert model.is_field_modified("b")
        assert model._persistent_values == {"a": old_value_a, "b": old_value_b}

        model._update_persistent_values(field_a, 66)
        assert model.is_field_modified("a")
        assert model.is_field_modified("b")
        assert model._persistent_values == {"a": old_value_a, "b": old_value_b}

        model._update_persistent_values(field_a, old_value_a)
        assert not model.is_field_modified("a")
        assert model.is_field_modified("b")
        assert model._persistent_values == {"b": old_value_b}

        model._update_persistent_values(field_b, old_value_b)
        assert not model.is_field_modified("b")
        assert model._persistent_values == {}

    def test_model_update_dispatch(self):
        called = False
        called_instance = None

        model = ModelA()

        def listen(instance, field, value):
            nonlocal called, called_instance
            called = True
            called_instance = instance
            assert field.name == "a"
            assert value == 2

        model._listener.subscribe(MODEL_UPDATE_EVENT, listen)  # type: ignore

        model.a = 2

        assert called
        assert id(called_instance) == id(model)
        assert model._persistent_values == {}

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
