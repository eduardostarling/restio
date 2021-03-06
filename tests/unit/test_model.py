from __future__ import annotations

import itertools
from enum import IntEnum
from typing import Any, Dict
from uuid import UUID, uuid4

import pytest

from restio.event import EventListener
from restio.fields import (
    BoolField,
    EnumField,
    FloatField,
    FrozenSetField,
    FrozenSetModelField,
    IntField,
    ModelField,
    StrField,
    TupleField,
    TupleModelField,
    UUIDField,
)
from restio.model import MODEL_UPDATE_EVENT, BaseModel, ModelMeta

default_uuid = UUID("31c6b6f9-bb10-4254-b0a5-77caa238933e")
default_uuid2 = UUID("3d88baf6-d52c-413e-8e03-9fcd730dde5e")


class TestModelPrimaryKeys:

    _pk_params = [
        (IntField, 1),
        (StrField, "a"),
        (UUIDField, default_uuid),
    ]

    @pytest.mark.parametrize("field_type, value", _pk_params)
    def test_primary_key_types(self, field_type, value):
        class Model(BaseModel):
            pk = field_type(pk=True)

        model = Model(pk=value)

        assert model.pk == value
        assert model.primary_keys == dict(pk=value)

    _compound_pk_params = itertools.product(_pk_params, _pk_params)

    @pytest.mark.parametrize("field_1, field_2", _compound_pk_params)
    def test_compound_primary_key_types(self, field_1, field_2):
        field_type1, value1 = field_1
        field_type2, value2 = field_2

        class Model(BaseModel):
            pk1 = field_type1(pk=True)
            pk2 = field_type2(pk=True)

        model = Model(pk1=value1, pk2=value2)

        assert model.pk1 == value1
        assert model.pk2 == value2
        assert model.primary_keys == dict(pk1=value1, pk2=value2)

    @pytest.mark.parametrize(
        "field_type, value",
        [(IntField, 1.0), (StrField, 1), (UUIDField, str(default_uuid)),],
    )
    def test_primary_key_set_error(self, field_type, value):
        class Model(BaseModel):
            pk = field_type(pk=True)

        with pytest.raises(TypeError, match="should be of type"):
            model = Model(pk=value)

    @pytest.mark.parametrize(
        "field_type, value1, value2",
        [
            (IntField, 1, 2),
            (StrField, "a", "b"),
            (UUIDField, default_uuid, default_uuid2),
        ],
    )
    def test_primary_key_set_twice(self, field_type, value1, value2):
        class Model(BaseModel):
            pk = field_type(pk=True)

        model = Model(pk=value1)
        assert model.pk == value1
        assert model.primary_keys == dict(pk=value1)

        model.pk = value2
        assert model.pk == value2
        assert model.primary_keys == dict(pk=value2)


class IntEnumType(IntEnum):
    A = 1
    B = 2
    C = 3


class ModelA(BaseModel):
    id: IntField = IntField(default=0, pk=True)
    a: IntField = IntField(default=0)
    b: StrField = StrField(default="")
    c: TupleField = TupleField(str, default_factory=tuple)
    d: FrozenSetField = FrozenSetField(int, default_factory=frozenset)
    e: BoolField = BoolField(default=False)
    f: FloatField = FloatField(default=0.0)
    g: UUIDField = UUIDField(default=default_uuid)
    h: EnumField = EnumField(IntEnumType, default=IntEnumType.A)


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
                alias = "ParentModelAlias"

        class ChildModel(ParentModel):
            class Meta:
                init = True
                init_extra_ignore = False

        class GrandChildModel(ChildModel):
            class Meta:
                init = False
                init_extra_ignore = True
                alias = "GrandChildModelAlias"

        parent_model = ParentModel()
        child_model = ChildModel()
        grand_child_model = GrandChildModel()

        self._assert_model_meta(
            parent_model, {"init": False, "alias": "ParentModelAlias"}
        )
        self._assert_model_meta(
            child_model, {"init": True, "init_extra_ignore": False, "alias": None}
        )
        self._assert_model_meta(
            grand_child_model,
            {"init": False, "init_extra_ignore": True, "alias": "GrandChildModelAlias"},
        )

    def test_model_field_string_type_repeated_alias(self):
        with pytest.raises(ValueError, match="`A` is already used"):

            class ModelA(BaseModel):
                class Meta:
                    alias = "A"

            class ModelB(BaseModel):
                class Meta:
                    alias = "A"

    def test_model_field_string_type_repeated_model_name(self):
        with pytest.raises(ValueError, match="`ModelName` is already used"):
            type("ModelName", (BaseModel,), {})
            type("ModelName", (BaseModel,), {})

    def test_model_field_string_type_alias_match_other_model_name(self):
        with pytest.raises(ValueError, match="`OtherModelName` is already used"):

            class OtherModelName(BaseModel):
                pass

            class OneMoreModel(BaseModel):
                class Meta:
                    alias = "OtherModelName"

    def test_model_field_string_type_invalid_model_alias(self):
        with pytest.raises(TypeError, match="Provided type alias"):

            class DependentModel(BaseModel):
                field = ModelField(model_type="NonExistingModelAlias")

            DependentModel(field="anything")

    def test_all_field_types_in_model(self):
        class AllFieldsModel(BaseModel):
            int_key = IntField(pk=True)
            str_key = StrField(pk=True)
            int_field = IntField()
            str_field = StrField()
            bool_field = BoolField()
            float_field = FloatField()
            uuid_field = UUIDField()
            enum_field = EnumField(IntEnumType)
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
            "float_field",
            "uuid_field",
            "enum_field",
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
                {
                    "id": 0,
                    "a": 0,
                    "b": "",
                    "c": tuple(),
                    "d": frozenset(),
                    "e": False,
                    "f": 0.0,
                    "g": default_uuid,
                    "h": IntEnumType.A,
                },
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
            (FloatField, 1.0),
            (UUIDField, default_uuid),
            (lambda default: EnumField(IntEnumType, default=default), IntEnumType.A),
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

    def test_model_repr(self):
        class Model(BaseModel):
            a: IntField = IntField()
            b: StrField = StrField()
            c: IntField = IntField(repr=False)

        model = Model(a=1, b="text", c=2)
        repr_str = repr(model)

        assert repr_str == "Model(a=1, b='text')"

    def test_model_repr_disabled(self):
        class Model(BaseModel):
            class Meta:
                repr = False

            a: IntField = IntField()
            b: StrField = StrField()
            c: IntField = IntField(repr=False)

        model = Model(a=1, b="text", c=2)
        repr_str = repr(model)

        assert "=1" not in repr_str
        assert "='text'" not in repr_str
        assert "=2" not in repr_str

    def test_model_repr_model_dependencies(self):
        class Model(BaseModel):
            a: IntField = IntField()
            b: StrField = StrField(default="")
            c: ModelField = ModelField(BaseModel)
            d: TupleField = TupleField(BaseModel, default_factory=tuple)

        model_a = Model(a=1)
        model_b = Model(a=2, b="text", c=model_a)
        model_c = Model(a=3, d=(model_a, model_b))

        repr_a = repr(model_a)
        repr_b = repr(model_b)
        repr_c = repr(model_c)

        assert repr_a == "Model(a=1, b='', c=None, d=())"
        assert repr_b == "Model(a=2, b='text', c=%s, d=())" % repr_a
        assert repr_c == "Model(a=3, b='', c=None, d=(%s, %s))" % (repr_a, repr_b)

    def test_model_repr_model_recursion(self):
        class Model(BaseModel):
            c: ModelField = ModelField(BaseModel)

        model = Model()
        model.c = model

        repr_model = repr(model)

        assert "Model(c=Model(c=Model" in repr_model
        assert "..." in repr_model
        assert ")))" in repr_model
        assert len(repr_model) >= 200
