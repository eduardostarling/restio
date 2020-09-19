from __future__ import annotations

from enum import IntEnum
from uuid import UUID, uuid4

import pytest

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
from restio.fields.base import Field, FrozenType
from restio.model import BaseModel


class IntEnumType(IntEnum):
    A = 1
    B = 2
    C = 3


class FieldsModel(BaseModel):
    id: IntField = IntField(default=0, pk=True)
    a: IntField = IntField(default=0)
    b: StrField = StrField(default="")


default_model = FieldsModel()
default_uuid = UUID("6564d955-5fb9-4731-9452-2e0a49a46243")
default_uuid2 = UUID("f4135fa3-ec79-45aa-a6e4-f5470eca9e01")


class TestFields:
    def test_base_field_provide_both_defaults(self):
        with pytest.raises(ValueError, match="provided for both"):
            Field(
                type_=str,
                pk=False,
                allow_none=False,
                depends_on=False,
                frozen=FrozenType.NEVER,
                default="",
                default_factory=str,
            )

    def test_base_field_missing_defaults(self):
        class BaseFieldModel(BaseModel):
            field = Field(
                type_=str,
                pk=False,
                allow_none=False,
                depends_on=False,
                frozen=FrozenType.NEVER,
            )

        with pytest.raises(ValueError, match="default value not"):
            BaseFieldModel()

    def test_enum_field_wrong_type(self):
        with pytest.raises(TypeError):
            EnumField(int)  # type: ignore

    @pytest.mark.parametrize(
        "field_type, value",
        [
            (IntField(), "a"),
            (StrField(), 5),
            (BoolField(), "a"),
            (FloatField(), 1),
            (UUIDField(), "6564d955-5fb9-4731-9452-2e0a49a46243"),
            (EnumField(IntEnumType), 1),
            (TupleField(int), ["a"]),
            (FrozenSetField(str), {"b"}),
            (ModelField(FieldsModel), "s"),
            (TupleModelField(FieldsModel), ["a"]),
            (FrozenSetModelField(FieldsModel), {"b"}),
        ],
    )
    def test_set_field_invalid_value(self, field_type, value):
        class Model(BaseModel):
            field = field_type

        with pytest.raises(TypeError, match="should be of type"):
            Model(field=value)

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
            (lambda default: ModelField(FieldsModel, default=default), default_model),
            (
                lambda default: TupleModelField(FieldsModel, default_factory=default),
                lambda: (default_model,),
            ),
            (
                lambda default: FrozenSetModelField(
                    FieldsModel, default_factory=default
                ),
                lambda: frozenset({default_model}),
            ),
        ],
    )
    def test_model_fields_custom_default(self, field_type, default):
        field = field_type(default=default)

        assert field.default == default() if callable(default) else default

    @pytest.mark.parametrize(
        "field_type",
        [
            IntField(),
            StrField(),
            BoolField(),
            FloatField(),
            UUIDField(),
            EnumField(IntEnumType),
            TupleField(int),
            FrozenSetField(str),
            TupleModelField(FieldsModel),
            FrozenSetModelField(FieldsModel),
        ],
    )
    def test_set_field_none(self, field_type):
        class Model(BaseModel):
            field = field_type

        with pytest.raises(TypeError, match="should be of type"):
            Model(field=None)

    @pytest.mark.parametrize(
        "field_type",
        [
            IntField,
            StrField,
            BoolField,
            FloatField,
            UUIDField,
            lambda **args: EnumField(IntEnumType, **args),
            lambda **args: ModelField(FieldsModel, **args),
        ],
    )
    def test_default_none_when_allow_none(self, field_type):
        class Model(BaseModel):
            field = field_type(allow_none=True)

        obj = Model()

        assert obj.field is None

    @pytest.mark.parametrize(
        "field_type, expected_value",
        [
            (IntField, 1),
            (StrField, "a"),
            (BoolField, True),
            (FloatField, 1.0),
            (UUIDField, default_uuid),
            (lambda **args: EnumField(IntEnumType, **args), IntEnumType.A),
            (lambda **args: ModelField(FieldsModel, **args), default_model),
        ],
    )
    def test_default_not_none_when_allow_none(self, field_type, expected_value):
        class Model(BaseModel):
            field = field_type(default=expected_value, allow_none=True)

        obj = Model()

        assert obj.field == expected_value

    _setter_params = [
        (lambda **kwargs: IntField(default=0, **kwargs), 1, 2),
        (lambda **kwargs: StrField(default="", **kwargs), "a", "b"),
        (lambda **kwargs: BoolField(default=False, **kwargs), False, True),
        (lambda **kwargs: FloatField(default=0.0, **kwargs), 1.0, 2.0),
        (
            lambda **kwargs: UUIDField(default_factory=uuid4, **kwargs),
            default_uuid,
            default_uuid2,
        ),
        (
            lambda **kwargs: EnumField(IntEnumType, default=IntEnumType.A, **kwargs),
            IntEnumType.B,
            IntEnumType.C,
        ),
        (lambda **kwargs: TupleField(int, default_factory=tuple, **kwargs), (1,), (2,)),
        (
            lambda **kwargs: FrozenSetField(str, default_factory=frozenset, **kwargs),
            frozenset({"a"}),
            frozenset({"b"}),
        ),
        (
            lambda **kwargs: ModelField(FieldsModel, default=None, **kwargs),
            None,
            default_model,
        ),
        (
            lambda **kwargs: TupleModelField(
                FieldsModel, default_factory=tuple, **kwargs
            ),
            tuple(),
            (default_model,),
        ),
        (
            lambda **kwargs: FrozenSetModelField(
                FieldsModel, default_factory=frozenset, **kwargs
            ),
            frozenset(),
            frozenset({default_model}),
        ),
    ]

    @pytest.mark.parametrize("field_type, input_value, setter_value", _setter_params)
    @pytest.mark.parametrize(
        "setter_type", ["constructor", "decorator", "method_decorator"]
    )
    def test_setter_field_assignment(
        self, setter_type, field_type, input_value, setter_value
    ):
        initialized = False
        model_class = None

        def setter(model, value):
            assert isinstance(model, BaseModel)

            if initialized:
                assert value == input_value
                return setter_value
            else:
                return value

        if setter_type == "constructor":

            class ModelConstructor(BaseModel):
                field = field_type(setter=setter)

            model_class = ModelConstructor

        elif setter_type == "decorator":

            class ModelDecorator(BaseModel):
                field = field_type()

                @field.setter
                def field_setter(self, value):
                    return setter(self, value)

            model_class = ModelDecorator

        elif setter_type == "method_decorator":

            class ModelMethodDecorator(BaseModel):
                field = field_type()
                field_setter = field.setter(setter)

            model_class = ModelMethodDecorator

        if not model_class:
            pytest.fail("Setter type has not been properly defined")

        obj = model_class()
        initialized = True
        assert obj.field != setter_value
        obj.field = input_value
        assert obj.field == setter_value

    def test_setter_exception(self):
        class Model(BaseModel):
            field = IntField(default=20)

            @field.setter
            def field_setter(self, value: int):
                if value < 18:
                    raise ValueError()
                return value

        obj = Model()

        assert obj.field == 20

        with pytest.raises(ValueError):
            obj.field = 5

        assert obj.field == 20

    def test_property_setter(self):
        class Model(BaseModel):
            _field = IntField(default=15)

            @property
            def field(self):
                return self._field

            @field.setter
            def field(self, value: int):
                if value < 18:
                    raise ValueError()
                self._field = value

        obj = Model()

        assert obj.field == 15
        assert obj._field == 15

        obj.field = 20

        assert obj.field == 20
        assert obj._field == 20
