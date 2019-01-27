from __future__ import annotations

from typing import Generic, TypeVar, Dict, Tuple, List, Union, Type, Any, Optional, get_type_hints, overload, cast
from copy import deepcopy
from dataclasses import dataclass, field
from uuid import uuid4, UUID

from .state import ModelState

T = TypeVar('T', int, str)


class PrimaryKey(Generic[T]):
    value: Optional[T]
    _type: Type[T]

    def __init__(self, key_type: Type[T], value: Optional[T] = None) -> None:
        if key_type not in T.__constraints__:  # type: ignore
            raise TypeError(f"Provided type {key_type.__name__} is not allowed.")

        self._type = key_type
        self.set(value)

    def set(self, value: Optional[T]):
        if value is not None and not issubclass(type(value), self._type):
            raise RuntimeError(f"Primary key value must be of type {self._type.__name__}")

        self.value = value

    def get(self) -> Optional[T]:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PrimaryKey):
            return issubclass(other._type, self._type) and other.value == self.value
        else:
            return issubclass(type(other), self._type) and other == self.value

    def __hash__(self):
        return hash((self._type, self.value))


ValueKey = Union[T, PrimaryKey]


def mdataclass(*args, **kwargs):
    kwargs['eq'] = kwargs.get('eq', False)
    return dataclass(*args, **kwargs)


def pk(key_type: Type[T], default_value: Optional[T] = None, **kwargs):
    return field(default=PrimaryKey(key_type, default_value), **kwargs)


@mdataclass
class BaseModel(Generic[T]):
    _internal_id: UUID = field(default_factory=uuid4)
    _state: ModelState = field(init=False, repr=False, compare=False, hash=False, default=ModelState.CLEAN)
    _persistent_values: Dict[str, Any] = field(init=False, repr=False, compare=False, hash=False, default_factory=dict)
    _immutable: List[str] = field(
        default_factory=lambda: ['_immutable', '_internal_id', '_state', '_persistent_values'],
        repr=False,
        init=False,
        compare=False,
        hash=False
    )

    @staticmethod
    def __get_primary_keys(cls) -> Dict[str, type]:
        return {
            attr: t.__args__[0]
            for attr, t in get_type_hints(cls).items() if hasattr(t, '__origin__') and t.__origin__ is PrimaryKey
        }

    @staticmethod
    def __get_typed_fields(cls) -> Dict[str, type]:
        return {
            attr: t
            for attr, t in get_type_hints(cls).items()
            if not hasattr(t, '__origin__') or (hasattr(t, '__origin__') and t.__origin__ is not PrimaryKey)
        }

    def get_primary_keys(self) -> Tuple[PrimaryKey, ...]:
        return tuple([cast(PrimaryKey, getattr(self, key)) for key in self.__get_primary_keys(self)])

    def get_keys(self) -> Tuple[Optional[T], ...]:
        return tuple([key.get() for key in self.get_primary_keys()])

    @overload
    def set_keys(self, primary_keys: Tuple[ValueKey, ...]):
        ...

    @overload
    def set_keys(self, primary_keys: List[ValueKey]):
        ...

    @overload
    def set_keys(self, primary_keys: ValueKey):
        ...

    def set_keys(self, primary_keys):
        attrs = self.__get_primary_keys(self)

        if not attrs:
            raise RuntimeError("This object does not contain primary keys.")

        if isinstance(primary_keys, list):
            primary_keys = tuple(primary_keys)

        if not isinstance(primary_keys, tuple):
            primary_keys = (primary_keys,)

        if len(attrs) != len(primary_keys):
            raise RuntimeError("The number of primary keys provided is incompatible.")

        attr_keys = list(attrs.keys())
        attr_types = list(attrs.values())

        for index, primary_key in enumerate(primary_keys):
            if not isinstance(primary_key, PrimaryKey):
                primary_key = PrimaryKey(type(primary_key), primary_key)

            if not issubclass(attr_types[index], primary_key._type):
                raise RuntimeError(
                    f'Type {primary_key._type.__name__} on position {index} incompatible' +
                    ' with {attr_keys[index]} of type {attr_types[index].__name__}'
                )
            setattr(self, attr_keys[index], primary_key)

    def copy(self) -> BaseModel:  # noqa: F821
        return deepcopy(self)

    def _get_mutable_fields(self) -> Dict[str, Any]:
        attrs = set(BaseModel.__get_primary_keys(self.__class__)) | \
            set(BaseModel.__get_typed_fields(self.__class__))

        return {k: getattr(self, k) for k in (attrs - set(self._immutable))}

    def get_children(
        self, recursive: bool = False, children: List['BaseModel'] = None, top_level: Optional['BaseModel'] = None
    ) -> List['BaseModel']:

        if children is None:
            children = []

        if top_level:
            if self == top_level:
                return children

            if self not in children:
                children.append(self)
        else:
            top_level = self

        for value in self._get_mutable_fields().values():

            def check(child):
                if isinstance(child, BaseModel) and child not in children:
                    if recursive:
                        child.get_children(recursive, children, top_level)
                    else:
                        children.append(child)

            if isinstance(value, list) or isinstance(value, set):
                for item in value:
                    check(item)
            else:
                check(value)

        return children

    def _get_modified_values(self, model: 'BaseModel') -> Dict[str, Any]:
        if model != self:
            return {}

        return {
            attr: getattr(model, attr)
            for attr, value in self._get_mutable_fields().items() if value != getattr(model, attr)
        }

    def _get_persistent_model(self):
        model = self.copy()

        for attr, value in self._persistent_values.items():
            setattr(model, attr, value)

        return model

    def _rollback(self):
        for attr, value in self._persistent_values.items():
            setattr(self, attr, value)

        self._persistent_values = {}

    def _persist(self):
        self._persistent_values = {}

    def _update(self, model: 'BaseModel') -> bool:
        persistent_model = self._get_persistent_model()
        modified_values = persistent_model._get_modified_values(model)

        self._persistent_values = {}

        for attr in self._get_mutable_fields():
            persistent_value = getattr(persistent_model, attr)
            if attr in modified_values:
                setattr(self, attr, modified_values[attr])
                self._persistent_values[attr] = persistent_value
            else:
                setattr(self, attr, persistent_value)

        return bool(modified_values)

    def __eq__(self, other):
        if other and isinstance(other, type(self)):
            return self._internal_id == other._internal_id

        return False

    def __hash__(self):
        return hash(str(self._internal_id))
