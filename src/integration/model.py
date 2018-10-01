
from typing import Optional, Generic, TypeVar, Dict, get_type_hints, Type
from uuid import uuid4, UUID

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
        return isinstance(other, PrimaryKey) and \
               isinstance(other.value, type(self.value)) and \
               self.value == other.value

    def __hash__(self):
        return self.value


class BaseModel(Generic[T]):
    _internal_id: UUID
    _default_primary_key: Optional[str] = None

    @staticmethod
    def __get_primary_keys(cls) -> Dict[str, type]:
        return {attr: t.__args__[0] for attr, t in get_type_hints(cls).items()
                if hasattr(t, '__origin__') and t.__origin__ is PrimaryKey}

    def __new__(cls, *args, **kwargs):
        attrs = BaseModel.__get_primary_keys(cls)
        instance = super().__new__(cls)

        default_key = kwargs.get('default_primary_key', None)

        if attrs:
            if default_key:
                if default_key not in attrs:
                    raise RuntimeError("Provided default PrimaryKey does not exist.")

                instance._default_primary_key = default_key
            else:
                for attr_pk, attr_type in attrs.items():
                    if not instance._default_primary_key and attr_type is int:
                        instance._default_primary_key = attr_pk

                    if issubclass(attr_type, int):
                        setattr(instance, attr_pk, PrimaryKey(0))
                    elif issubclass(attr_type, str):
                        setattr(instance, attr_pk, PrimaryKey(""))

            if not instance._default_primary_key:
                instance._default_primary_key = list(attrs.keys())[0]

        return instance

    def __init__(self, uuid: Optional[UUID] = None) -> None:
        self._internal_id = uuid if uuid else uuid4()

    def _get_key_attribute(self, key_type: Optional[Type[T]] = None) -> str:
        if not key_type:
            if not self._default_primary_key:
                raise RuntimeError("This object does not contain a default primary key defined. \
                            You must define at least one PrimaryKey property.")

            return self._default_primary_key

        for attr_pk, attr_type in self.__get_primary_keys(self).items():
            if issubclass(attr_type, key_type):
                return attr_pk

        raise RuntimeError(f'No PrimaryKey with type {key_type.__name__} has been found')

    def _check_primary_key(self, attr_pk: str):
        if attr_pk not in self.__get_primary_keys(self):
            raise RuntimeError(f'Key attribute {attr_pk} does not exist in current object.')

    def get_key(self, key_type: Optional[Type[T]] = None) -> T:
        attr_pk = self._get_key_attribute(key_type)
        self._check_primary_key(attr_pk)

        return getattr(self, attr_pk).get()

    def set_key(self, value: T, key_type: Optional[Type[T]] = None):
        attr_pk = self._get_key_attribute(key_type)
        self._check_primary_key(attr_pk)

        getattr(self, attr_pk).set(value)

    def __hash__(self):
        return str(self._internal_id)

    def __eq__(self, other):
        if other and isinstance(other, type(self)):
            return self.__hash__() == other.__hash__()

        return False


class Model(BaseModel):
    id: PrimaryKey[int]
    key: PrimaryKey[str]
    k: Optional[str]
