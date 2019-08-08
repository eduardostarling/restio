from __future__ import annotations

from dataclasses import dataclass, field, is_dataclass
from typing import (Any, ClassVar, Dict, ForwardRef, Generic, List, Optional,
                    Set, Tuple, Type, TypeVar, Union)
from uuid import UUID, uuid4

from .event import EventListener
from .state import ModelState


class _DefaultPrimaryKey:
    def __eq__(self, value):
        if isinstance(value, _DefaultPrimaryKey) or value is None:
            return True
        return False

    def __hash__(self):
        return hash(None)


DefaultPrimaryKey = _DefaultPrimaryKey()


T = TypeVar('T', int, str, _DefaultPrimaryKey)


class PrimaryKey(Generic[T]):
    value: T
    _type: Type[T]

    def __init__(self, key_type: Type[T], value: T = DefaultPrimaryKey) -> None:
        if key_type not in T.__constraints__:  # type: ignore
            raise TypeError(f"Provided type {key_type.__name__} is not allowed.")

        self._type = key_type
        self.set(value)

    def set(self, value: T):
        if value is not DefaultPrimaryKey and not issubclass(type(value), self._type):
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
        return hash((self._type, self.value))


ValueKey = Union[T, PrimaryKey]


def mdataclass(*args, **kwargs):
    kwargs['eq'] = kwargs.get('eq', False)
    return dataclass(*args, **kwargs)


def pk(key_type: Type[T], default_value: T = DefaultPrimaryKey, **kwargs):
    return field(default_factory=lambda: PrimaryKey(key_type, default_value), **kwargs)


class BaseModelMeta(type):
    _class_mutable: Set[str]
    _class_immutable: Set[str]

    def __new__(cls, name, bases, dct):
        x: BaseModel = super().__new__(cls, name, bases, dct)

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


MODEL_UPDATE_EVENT = "__updated__"


@mdataclass
class BaseModel(Generic[T], metaclass=BaseModelMeta):
    _class_primary_keys: ClassVar[Dict[str, type]]
    _class_typed_fields: ClassVar[Dict[str, type]]
    _class_mutable: ClassVar[Set[str]]
    _class_immutable: ClassVar[Set[str]]

    _internal_id: UUID = field(default_factory=uuid4)
    _state: ModelState = field(init=False, repr=False, compare=False, hash=False, default=ModelState.CLEAN)
    _persistent_values: Dict[str, Any] = field(init=False, repr=False, compare=False, hash=False, default_factory=dict)
    _primary_keys: Tuple[Optional[T], ...] = field(repr=False, init=False, compare=False, hash=False)
    _listener: EventListener = field(repr=False, init=False, compare=False, hash=False, default_factory=EventListener)
    _initialized: bool = field(repr=False, init=False, compare=False, hash=False, default=False)

    def __post_init__(self):
        self._initialized = True
        self._primary_keys = self._get_primary_keys()

    def _get_primary_keys(self) -> Tuple[Optional[T], ...]:
        return tuple([
            getattr(self, key)
            for key in self._class_primary_keys])

    def get_keys(self) -> Tuple[Optional[T], ...]:
        return self._primary_keys

    def _get_mutable_fields(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self._class_mutable}

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

    def _rollback(self):
        for attr, value in list(self._persistent_values.items()):
            setattr(self, attr, value)

        self._persistent_values = {}

    def _persist(self):
        self._persistent_values = {}

    def _update(self, name, value):
        if not self._initialized:
            return

        if name in self._persistent_values:
            if value == self._persistent_values[name]:
                del self._persistent_values[name]
        else:
            mutable_fields = self._get_mutable_fields()
            if value != mutable_fields[name]:
                self._persistent_values[name] = mutable_fields[name]

        self._listener.dispatch(MODEL_UPDATE_EVENT, self)

    def __eq__(self, other):
        if other and isinstance(other, type(self)):
            return self._internal_id == other._internal_id

        return False

    def __hash__(self):
        return hash(str(self._internal_id))

    def __setattr__(self, name, value):
        if name in self._class_primary_keys:
            if not isinstance(value, PrimaryKey):
                key_type = self._class_primary_keys[name]
                value = PrimaryKey(key_type, value)

            self._update(name, value)
            super().__setattr__(name, value)

            if self._initialized:
                self._primary_keys = self._get_primary_keys()

        elif name in self._class_mutable:
            self._update(name, value)
            super().__setattr__(name, value)
        else:
            super().__setattr__(name, value)

    def __getattribute__(self, name):
        initialized = object.__getattribute__(self, '_initialized')

        if initialized:
            cls = object.__getattribute__(self, '__class__')
            if name in cls._class_primary_keys:
                key_attr = super().__getattribute__(name)

                if isinstance(key_attr, PrimaryKey):
                    return key_attr.get()
                else:
                    return key_attr

        return super().__getattribute__(name)
