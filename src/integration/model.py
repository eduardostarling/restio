
from __future__ import annotations
from typing import Optional, Generic, TypeVar, Dict, Tuple, List, Union, Type, Any, get_type_hints, overload
from copy import deepcopy
from enum import Enum
from uuid import uuid4, UUID


class ModelState(Enum):
    CLEAN = 0
    NEW = 1
    DIRTY = 2
    DELETED = 3
    DISCARDED = 4


T = TypeVar('T', int, str)


class PrimaryKey(Generic[T]):
    value: T
    _type: Type[T]

    def __init__(self, value: T) -> None:
        self._type = type(value)
        self.set(value)

    def set(self, value: T):
        if not issubclass(type(value), self._type):
            raise RuntimeError(f"Primary key value must be of type {self._type.__name__}")

        self.value = value

    def get(self) -> T:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PrimaryKey):
            return issubclass(other._type, self._type) and other.value == self.value
        else:
            return issubclass(type(other), self._type) and other == self.value

    def __hash__(self):
        return self.value


ValueKey = Union[T, PrimaryKey]


class BaseModel(Generic[T]):
    _internal_id: UUID
    _state: ModelState = ModelState.CLEAN

    _immutable: List[str] = ['_immutable', '_internal_id', '_state']

    @staticmethod
    def __get_primary_keys(cls) -> Dict[str, type]:
        return {attr: t.__args__[0] for attr, t in get_type_hints(cls).items()
                if hasattr(t, '__origin__') and t.__origin__ is PrimaryKey}

    @staticmethod
    def __get_typed_fields(cls) -> Dict[str, type]:
        return {attr: t for attr, t in get_type_hints(cls).items()
                if not hasattr(t, '__origin__') or (hasattr(t, '__origin__') and t.__origin__ is not PrimaryKey)}

    def __new__(cls, *args, **kwargs):
        attrs = BaseModel.__get_primary_keys(cls)
        fields = BaseModel.__get_typed_fields(cls)

        instance = super().__new__(cls)

        primary_keys: Optional[Tuple[ValueKey, ...]] = kwargs.get('primary_keys', [])

        if attrs:
            if not primary_keys:
                for attr_pk, attr_type in attrs.items():
                    if issubclass(attr_type, int):
                        primary_keys.append(PrimaryKey(0))
                    elif issubclass(attr_type, str):
                        primary_keys.append(PrimaryKey(""))

            instance.set_keys(primary_keys)
        elif primary_keys:
            raise RuntimeError("This model does not contain primary keys.")

        for field in fields.keys():
            if not hasattr(instance, field):
                setattr(instance, field, None)

        return instance

    def __init__(self, uuid: Optional[UUID] = None, *args, **kwargs) -> None:
        self._internal_id = uuid if uuid else uuid4()
        self._state = ModelState.CLEAN

    def get_primary_keys(self) -> Tuple[PrimaryKey, ...]:
        return tuple([getattr(self, key) for key in self.__get_primary_keys(self)])

    def get_keys(self) -> Tuple[T, ...]:
        return tuple([pk.get() for pk in self.get_primary_keys()])

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
                primary_key = PrimaryKey(primary_key)

            if not issubclass(attr_types[index], primary_key._type):
                raise RuntimeError(
                    f'Type {primary_key._type.__name__} on position {index} incompatible' +
                    ' with {attr_keys[index]} of type {attr_types[index].__name__}')
            setattr(self, attr_keys[index], primary_key)

    def copy(self) -> BaseModel:  # noqa: F821
        return deepcopy(self)

    def _get_mutable_fields(self) -> Dict[str, Any]:
        attrs = set(BaseModel.__get_primary_keys(self.__class__)) | \
            set(BaseModel.__get_typed_fields(self.__class__))

        return {k: getattr(self, k) for k in attrs - set(self._immutable)}

    def __hash__(self):
        return str(self._internal_id)

    def __eq__(self, other):
        if other and isinstance(other, type(self)):
            return self.__hash__() == other.__hash__()

        return False
