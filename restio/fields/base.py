import inspect
from enum import Flag, auto
from typing import TYPE_CHECKING, Callable, Generic, Optional, Type, TypeVar, Union

from restio.shared import MODEL_TYPE_REGISTRY

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
    """
    Base type for Fields.
    """

    type_: Union[Type[T_co], str]
    name: str
    init: bool
    pk: bool
    allow_none: bool
    depends_on: bool
    frozen: FrozenType
    repr: bool
    type_check: bool

    _default: Optional[T_co]
    _default_factory: Optional[Callable[[], T_co]]
    _setter: Optional[SetterType]

    def __init__(
        self,
        type_: Union[Type[T_co], str],
        *,
        pk: bool,
        allow_none: bool,
        depends_on: bool,
        frozen: FrozenType,
        init: bool = True,
        default: Union[Optional[T_co], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], T_co]], Type[MISSING]] = MISSING,
        setter: Optional[SetterType] = None,
        repr: bool = True,
        type_check: bool = True,
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
        self.init = init
        self.allow_none = allow_none
        self.depends_on = depends_on
        self.frozen = frozen
        self.setter(setter)
        self.repr = repr
        self.type_check = type_check

        # post-assignment validation
        self._validate_string_type(self.type_)

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
        if self.type_check:
            self._cache_string_field_type(instance)
            _check_field_value_type(
                self.type_,  # type: ignore
                self._field_name(instance),
                value,
                allow_none=self.allow_none,
            )
        return self._setter(instance, value) if self._setter is not None else value

    def _cache_string_field_type(self, instance: "BaseModel"):
        # this is a one-off operation, for the first check
        if not isinstance(self.type_, str):
            return

        self.type_ = self._parse_string_field_type(instance, self.type_)  # type: ignore

    def _parse_string_field_type(
        self, instance: "BaseModel", type_: str
    ) -> Union[Type[T_co], Type[SubT]]:
        if type_ not in MODEL_TYPE_REGISTRY:
            raise TypeError(
                f"Provided type alias `{type_}` for field "
                "`{self._field_name(instance)}` is not valid."
            )

        return MODEL_TYPE_REGISTRY[type_]

    def _validate_string_type(self, type_: Union[Type[T_co], str]):
        if not self.type_check:
            return

        if not isinstance(type_, str):
            return

        if not self.depends_on:
            raise TypeError(
                f"Type string `{type_}` is invalid for non-relational field."
            )

    @property
    def default(self) -> T_co:
        """
        Extracts the default value of the field.

        :raises ValueError: When no default value has been set during initialization.
        :return: The default value.
        """
        if not self.has_default:
            raise ValueError(
                f"Can't initialize field {self.name}: default value not provided."
            )

        return (
            self._default_factory()
            if self._default_factory is not MISSING
            else self._default
        )

    @property
    def has_default(self) -> bool:
        """
        Indicates if the field has a default value set during the initialization.

        :return: True if a default value has been set, False otherwise.
        """
        return self._default is not MISSING or self._default_factory is not MISSING

    def setter(self, method: Optional[SetterType]):
        """
        Defines the setter function `method` for the current field. `method` is only
        triggered when a value is assigned to the field through the descriptor
        protocol.

        :param method: The method to be called for setting the value. Method should
                       accept 2 parameters and must return the value to be assigned
                       to the field. The first parameter will contain the instance
                       from which the setter was called, and the second will contain
                       the value assigned.
        :raises ValueError: When the signature of `method` is incorrect.
        :return: The decorated `method`.
        """
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


class ContainerField(Field[T_co], Generic[T_co, SubT]):
    sub_type: Union[Type[SubT], str]

    def __init__(
        self,
        type_: Union[Type[T_co], str],
        sub_type: Union[Type[SubT], str],
        *,
        pk: bool,
        allow_none: bool,
        depends_on: bool,
        frozen: FrozenType,
        init: bool = True,
        default: Union[Optional[T_co], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], T_co]], Type[MISSING]] = MISSING,
        setter: Optional[SetterType] = None,
        repr: bool = True,
        type_check: bool = True,
    ) -> None:
        super().__init__(
            type_=type_,
            pk=pk,
            init=init,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=depends_on,
            frozen=frozen,
            setter=setter,
            repr=repr,
            type_check=type_check,
        )
        self.sub_type = sub_type

        self._validate_string_type(self.sub_type)

    def _check_sub_value(self, instance: "BaseModel", sub_value: SubT):
        if self.type_check:
            self._cache_string_field_type(instance)

            _check_field_value_type(
                self.sub_type,  # type: ignore
                self.name,
                sub_value,
            )

    def _cache_string_field_type(self, instance: "BaseModel"):
        super()._cache_string_field_type(instance)

        if not isinstance(self.sub_type, str):
            return

        self.sub_type = self._parse_string_field_type(  # type: ignore
            instance, self.sub_type
        )


class IterableField(ContainerField[T_co, SubT]):
    def __init__(
        self,
        type_: Union[Type[T_co], str],
        sub_type: Union[Type[SubT], str],
        *,
        allow_none: bool,
        depends_on: bool,
        frozen: FrozenType,
        init: bool = True,
        default: Union[Optional[T_co], Type[MISSING]] = MISSING,
        default_factory: Union[Optional[Callable[[], T_co]], Type[MISSING]] = MISSING,
        setter: Optional[SetterType] = None,
        repr: bool = True,
        type_check: bool = True,
    ) -> None:
        super().__init__(
            type_=type_,
            sub_type=sub_type,
            pk=False,
            init=init,
            default=default,
            default_factory=default_factory,
            allow_none=allow_none,
            depends_on=depends_on,
            frozen=frozen,
            setter=setter,
            repr=repr,
            type_check=type_check,
        )

    def _check_value(self, instance: "BaseModel", value: SubT):
        if self.type_check:
            value = super()._check_value(instance, value)
            for item in value:
                super()._check_sub_value(instance, item)
        return value
