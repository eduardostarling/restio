import inspect
from enum import Flag, auto
from typing import TYPE_CHECKING, Callable, Generic, Optional, Type, TypeVar, Union

if TYPE_CHECKING:
    from restio.model import BaseModel


Model_co = TypeVar("Model_co", bound="BaseModel", covariant=True)
T_co = TypeVar("T_co", bound=object, covariant=True)
SubT = TypeVar("SubT")


def _check_field_value_type(
    type_: Type, name: str, value: T_co, allow_none: bool = False
):
    if allow_none and value is None:
        return

    if not isinstance(value, type_):
        raise TypeError(f"Value of `{name}` should be of type {type_.__name__}")


class MISSING:
    pass


class FrozenType(Flag):
    """
    Indicates when a particular field should not be modified.

    - NEVER: The field can be modified at any time (read and write).
    - UPDATE: The field should be read-only for a model update.
    - CREATE: The field should be read-only when creating the model.
    - ALWAYS: The field is always read-only.
    """

    NEVER = auto()
    UPDATE = auto()
    CREATE = auto()
    ALWAYS = UPDATE | CREATE  # type: ignore


SetterType = Callable[[Model_co, T_co], T_co]

# Base fields


class Field(Generic[T_co], object):
    type_: Type[T_co]
    name: str
    _default: Optional[T_co]
    _default_factory: Optional[Callable[[], T_co]]
    pk: bool
    allow_none: bool
    depends_on: bool
    frozen: FrozenType
    _setter: Optional[SetterType]

    def __init__(
        self,
        type_: Type[T_co],
        *,
        pk: bool,
        allow_none: bool,
        depends_on: bool,
        frozen: FrozenType,
        default: Union[Optional[T_co], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], T_co]], Type[MISSING]] = MISSING,
        setter: Optional[SetterType] = None,
    ):
        if default is MISSING and default_factory is MISSING:
            if allow_none:
                default = None

        if default is not MISSING and default_factory is not MISSING:
            raise ValueError(
                "Default value for field provided for both `default` and"
                " `default_factory`"
            )

        self.type_ = type_
        self._default = default
        self._default_factory = default_factory
        self.pk = pk
        self.allow_none = allow_none
        self.depends_on = depends_on
        self.frozen = frozen
        self.setter(setter)

    def __set_name__(self, owner, name: str):
        self.name = name

    def __set__(self, instance: "BaseModel", value: T_co):
        if instance._initialized:
            instance._pre_update(self, value)

        value = self._check_value(instance, value)

        if instance._initialized:
            instance._update(self, value)

        instance.__dict__[self.name] = value

    def __get__(self, instance: "BaseModel", cls=None) -> T_co:
        if instance is None:
            return self

        self._store_default(instance, force=False)

        return instance.__dict__[self.name]

    def __delete__(self, instance: "BaseModel") -> None:
        del instance.__dict__[self.name]

    def _store_default(self, instance: "BaseModel", force=False):
        if self.name not in instance.__dict__ or force:
            default = self._check_value(instance, self.default)
            instance.__dict__[self.name] = default

    def _check_value(self, instance: "BaseModel", value: T_co) -> T_co:
        _check_field_value_type(
            self.type_, self._field_name(instance), value, allow_none=self.allow_none
        )
        return self._setter(instance, value) if self._setter is not None else value

    @property
    def default(self) -> T_co:
        if self._default is MISSING and self._default_factory is MISSING:
            raise ValueError(f"Default value not defined for field {self.name}.")

        return (
            self._default_factory()
            if self._default_factory is not MISSING
            else self._default
        )

    def setter(self: "Field[T_co]", method: Optional[SetterType]):
        if method is not None:
            signature = inspect.signature(method).parameters
            if len(signature) != 2:
                raise ValueError(
                    f"The provided setter {method.__name__} should accept exactly 2"
                    " parameters."
                )
        self._setter = method
        return method

    def _field_name(self, instance: "BaseModel") -> str:
        return f"{instance.__class__.__name__}.{self.name}"


class ContainerField(Field[T_co]):
    sub_type: Type[SubT]

    def __init__(
        self,
        type_: Type[T_co],
        sub_type: Type[SubT],
        *,
        pk: bool,
        allow_none: bool,
        depends_on: bool,
        frozen: FrozenType,
        default: Union[Optional[T_co], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], T_co]], Type[MISSING]] = MISSING,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            type_=type_,
            pk=pk,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=depends_on,
            frozen=frozen,
            setter=setter,
        )
        self.sub_type = sub_type

    def _check_sub_value(self, sub_value: SubT):
        _check_field_value_type(self.sub_type, self.name, sub_value)


class IterableField(ContainerField[T_co]):
    def __init__(
        self,
        type_: Type[T_co],
        sub_type: Type[SubT],
        *,
        allow_none: bool,
        depends_on: bool,
        frozen: FrozenType,
        default: Union[Optional[T_co], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], T_co]], Type[MISSING]] = MISSING,
        setter: Optional[SetterType] = None,
    ) -> None:
        super().__init__(
            type_=type_,
            sub_type=sub_type,
            pk=False,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=depends_on,
            frozen=frozen,
            setter=setter,
        )

    def _check_value(self, instance: "BaseModel", value: SubT):
        value = super()._check_value(instance, value)
        for item in value:
            super()._check_sub_value(item)
        return value
