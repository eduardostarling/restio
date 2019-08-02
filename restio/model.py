from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, is_dataclass
from typing import (Any, Dict, ForwardRef, Generic, List, Optional, Set, Tuple,
                    Type, TypeVar, Union, cast, overload)
from uuid import UUID, uuid4

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


class BaseModelMeta(type):
    def __new__(cls, name, bases, dct):
        x = super().__new__(cls, name, bases, dct)

        if name == 'BaseModel' or is_dataclass(x):
            x._class_primary_keys = {}
            x._class_typed_fields = {}
            x._class_mutable = set()
            x._class_immutable = set()

            for base in bases:
                if is_dataclass(base):
                    try:
                        x._class_primary_keys.update(base._class_primary_keys)
                        x._class_typed_fields.update(base._class_typed_fields)
                        x._class_immutable.update(base._class_immutable)
                    except Exception:
                        pass

            ann = dct.get('__annotations__', [])
            for field_name, field_type in ann.items():
                if field_name.startswith('_'):
                    x._class_immutable.add(field_name)
                else:
                    field_type = cls.evaluate_type(field_type)
                    if cls.is_primary_key(field_type):
                        x._class_primary_keys.update({field_name: cls.primary_key_type(field_type)})
                    else:
                        x._class_typed_fields.update({field_name: field_type})

            mutable = (set(x._class_primary_keys.keys()) | set(x._class_typed_fields.keys())) - set(x._class_immutable)
            x._class_mutable = mutable

        return x

    @classmethod
    def evaluate_type(cls, field_type):
        if isinstance(field_type, str):
            try:
                return ForwardRef(field_type, is_argument=False)._evaluate(globals(), locals())
            except Exception:
                pass

        return field_type

    @classmethod
    def is_primary_key(cls, field_type):
        return hasattr(field_type, '__origin__') and field_type.__origin__ is PrimaryKey

    @classmethod
    def primary_key_type(cls, field_type):
        return field_type.__args__[0]


@mdataclass
class BaseModel(Generic[T], metaclass=BaseModelMeta):
    _internal_id: UUID = field(default_factory=uuid4)
    _state: ModelState = field(init=False, repr=False, compare=False, hash=False, default=ModelState.CLEAN)
    _persistent_values: Dict[str, Any] = field(init=False, repr=False, compare=False, hash=False, default_factory=dict)
    _primary_keys: Tuple[Optional[T], ...] = field(repr=False, init=False, compare=False, hash=False)
    _typed_fields: Dict[str, type] = field(repr=False, init=False, compare=False, hash=False)
    _mutable: Set[str] = field(repr=False, init=False, compare=False, hash=False)
    _immutable: Set[str] = field(repr=False, init=False, compare=False, hash=False)

    def __post_init__(self):
        self._primary_keys = self.get_primary_keys()
        self._typed_fields = self.__class__._class_typed_fields
        self._mutable = self.__class__._class_mutable
        self._immutable = self.__class__._class_immutable

    def get_primary_keys(self) -> Tuple[Optional[T], ...]:
        return tuple([
            cast(PrimaryKey, getattr(self, key)).get()
            for key in self.__class__._class_primary_keys])

    def get_keys(self) -> Tuple[Optional[T], ...]:
        return self._primary_keys

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
        keys = self.__class__._class_primary_keys
        if not keys:
            raise RuntimeError("This object does not contain primary keys.")

        if isinstance(primary_keys, list):
            primary_keys = tuple(primary_keys)

        if not isinstance(primary_keys, tuple):
            primary_keys = (primary_keys,)

        if len(keys) != len(primary_keys):
            raise RuntimeError("The number of primary keys provided is incompatible.")

        attr_keys = list(keys.keys())
        attr_types = list(keys.values())

        for index, primary_key in enumerate(primary_keys):
            if not isinstance(primary_key, PrimaryKey):
                primary_key = PrimaryKey(type(primary_key), primary_key)

            if not issubclass(attr_types[index], primary_key._type):
                raise RuntimeError(
                    f'Type {primary_key._type.__name__} on position {index} incompatible' +
                    f' with {attr_keys[index]} of type {attr_types[index].__name__}'
                )
            setattr(self, attr_keys[index], primary_key)

        self._primary_keys = primary_keys

    def copy(self) -> BaseModel:  # noqa: F821
        return deepcopy(self)

    def _get_mutable_fields(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self._mutable}

    def get_children(
        self, recursive: bool = False, children: List[BaseModel] = None, top_level: Optional[BaseModel] = None
    ) -> List[BaseModel]:

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

    def _update(self, model: BaseModel) -> bool:
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
