from __future__ import annotations

import pytest

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
from restio.fields.base import Field, FrozenType
from restio.model import BaseModel


class FieldsModel(BaseModel):
    id: IntField = IntField(pk=True)
    a: IntField = IntField()
    b: StrField = StrField()


default_model = FieldsModel()


class TestFields:
    def test_base_field_provide_both_defaults(self):
        with pytest.raises(ValueError, match="provided for both"):

            class BaseFieldModel(BaseModel):
                field = Field(
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

        with pytest.raises(ValueError):
            BaseFieldModel()

    def test_all_fields(self):
        class AllFieldsModel(BaseModel):
            int_key = IntField(pk=True)
            str_key = StrField(pk=True)
            int_field = IntField()
            str_field = StrField()
            bool_field = BoolField()
            tuple_field = TupleField(str)
            set_field = FrozenSetField(int)
            model_field = ModelField(FieldsModel)
            tuple_model_field = TupleModelField(FieldsModel)
            set_model_field = FrozenSetModelField(FieldsModel)
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
        "field_type, default",
        [
            (IntField(), 0),
            (StrField(), ""),
            (BoolField(), False),
            (TupleField(int), tuple()),
            (FrozenSetField(str), frozenset()),
            (ModelField(FieldsModel), None),
            (TupleModelField(FieldsModel), tuple()),
            (FrozenSetModelField(FieldsModel), frozenset()),
        ],
    )
    def test_field_default(self, field_type, default):
        class Model(BaseModel):
            field = field_type

        obj = Model()

        assert Model._meta.fields.keys() == {"field"}
        assert obj.field == default

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
    def test_field_custom_default(self, field_type, default):
        class Model(BaseModel):
            field = field_type(default=default)

        obj = Model()

        assert Model._meta.fields.keys() == {"field"}
        assert obj.field == default() if callable(default) else default

    @pytest.mark.parametrize(
        "field_type, value",
        [
            (IntField(), "a"),
            (StrField(), 5),
            (BoolField(), "a"),
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

        obj = Model()

        with pytest.raises(TypeError, match="should be of type"):
            obj.field = value

    @pytest.mark.parametrize(
        "field_type",
        [
            IntField(),
            StrField(),
            BoolField(),
            TupleField(int),
            FrozenSetField(str),
            TupleModelField(FieldsModel),
            FrozenSetModelField(FieldsModel),
        ],
    )
    def test_set_field_none(self, field_type):
        class Model(BaseModel):
            field = field_type

        obj = Model()

        with pytest.raises(TypeError, match="should be of type"):
            obj.field = None

    @pytest.mark.parametrize(
        "field_type",
        [
            IntField,
            StrField,
            BoolField,
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
            (lambda **args: ModelField(FieldsModel, **args), default_model),
        ],
    )
    def test_default_not_none_when_allow_none(self, field_type, expected_value):
        class Model(BaseModel):
            field = field_type(default=expected_value, allow_none=True)

        obj = Model()

        assert obj.field == expected_value
