from __future__ import annotations

import types
from collections.abc import Iterable
from dataclasses import dataclass
from functools import wraps
from typing import (Any, Dict, Generic, List, Optional, Set, Tuple, Type,
                    TypeVar, Union)
from uuid import UUID, uuid4

from .event import EventListener
from .state import ModelState

T = TypeVar('T', int, str, None)


def _check_model_type(obj: Optional[BaseModel]):
    if not isinstance(obj, BaseModel):
        raise TypeError("The provided object is not of type BaseModel.")


class PrimaryKey(Generic[T]):
    """
    Represents a primary key in a remote model, in a similar fashion as if
    it would be stored in a relational database. The PrimaryKey fields are
    arbitrary to the developer's choice and used to identify models on the
    internal cache, used as reference for retrieval from the remote server
    and represent model uniqueness within a Transaction scope.

    Each PrimaryKey is a generic type and should explicitly indicate the type
    during declaration in a BaseModel.
    """
    name: str
    _type: Type[T]

    def __init__(self, key_type: Type[T], **kwargs) -> None:
        if key_type not in T.__constraints__:  # type: ignore
            raise TypeError(f"Provided type {key_type.__name__} is not allowed.")

        self._type = key_type

    def __set_name__(self, owner, name: str):
        self.name = name

    def __set__(self, instance, value: T):
        """
        Sets the value of the PrimaryKey.

        :param value: The value contained by the PrimaryKey.
        :raises RuntimeError: If `value` is not of the type T specified during
                              the declaration of the instance.
        """
        if isinstance(value, PrimaryKey):
            value = None

        if value and not isinstance(value, self._type):
            raise RuntimeError(f"Primary key value must be of type {self._type.__name__}")

        instance.__dict__[self.name] = value

    def __get__(self, instance, owner) -> Union[T, PrimaryKey[T]]:
        """
        Returns the value stored by the PrimaryKey.

        :return: The value stored by the instance.
        """

        if instance is None:
            return self

        return instance.__dict__.setdefault(self.name, None)


ValueKey = Union[T, PrimaryKey[T]]
"""
Represents the Union of a PrimaryKey or the value stored by it.
"""


def mdataclass(*args, **kwargs):
    """
    Wrapper around the dataclass() decorator used to guarantee that subclasses of
    BaseModel are dataclasses constructed with the proper configuration. Only needed
    if any of the child classes are intended to be dataclasses.
    """
    kwargs['eq'] = kwargs.get('eq', False)

    def init_wrapper(init_method):
        @wraps(init_method)
        def init_func(self: BaseModel, *margs, **mkwargs):
            self.pre_setup_model()
            init_method(self, *margs, **mkwargs)
            self.post_setup_model()
        return init_func

    model_class = dataclass(*args, **kwargs)
    model_class.__init__ = init_wrapper(model_class.__init__)

    return model_class


class BaseModelMeta(type):
    """
    BaseModel metaclass. Responsible to internally cache the data schema in a
    BaseModel subclass by identifying fields that are primary keys, mutable and
    immutable.
    """
    _class_mutable: Set[str]
    _class_immutable: Set[str]

    def __new__(cls, name, bases, dct):
        x: BaseModel = super().__new__(cls, name, bases, dct)

        x._class_primary_keys = {}
        x._class_mutable = set()
        x._class_immutable = set()

        for base in bases:
            try:
                x._class_primary_keys.update(base._class_primary_keys)
                x._class_immutable.update(base._class_immutable)
            except Exception:
                pass

        for field_name, field_value in dct.items():
            if isinstance(field_value, types.FunctionType) or \
               field_name.startswith('__'):
                continue

            if field_name.startswith('_'):
                x._class_immutable.add(field_name)
            else:
                if isinstance(field_value, PrimaryKey):
                    x._class_primary_keys.update({field_name: field_value._type})
                x._class_mutable.add(field_name)

        return x


MODEL_UPDATE_EVENT = "__updated__"


class BaseModel(Generic[T], metaclass=BaseModelMeta):
    """
    A representation of a remote object model into a restio.Transaction object.

    BaseModel is an abstract class that should be extended to represent models incoming
    from or outgoing to a remote REST API. The subclasses can benefit from dataclasses
    by using the decorator @mdataclass.

    Models can exist independently from Transactions but contain an internal state that
    indicates the status of the model within the current context. The transactions are
    responsible to control this state. Also, each model contains a set of control attributes
    that indicate which fields are mutable, immutable or primary keys (provided by the
    BaseModelMeta).

    Models that change over time will contain an internal dictionary with the latest
    know persistent value of each field. This is done to guarantee fast rollback of the
    values when the Transaction is invalid, and to also indicate which values might have
    changed within the transaction scope. If a mutable field is modified directly, the model
    will intercept the change and save the older value into the persistent dictionary until
    `_persist` is called. During a `_rollback` call, however, the stored values are re-assigned
    to their original attributes. Each attribute change will also dispatch an update event so
    that the transaction is aware of changes and manages the model's internal state accordingly.
    The persistent dictionary can also be potentially used by DAO's to verify which values where
    updated prior to sending a request through the REST API, thus allowing for proper optimization
    and minimizing chances of conflicting changes on the remote object.

    All models automatically generate a random internal UUID when created. This UUID is used
    internally for comparison purposes, and externally as an identity.

    :Example:

    @mdataclass
    class Person(BaseModel):
        id: PrimaryKey[int] = PrimaryKey(int)
        name: str = ""
        age: int = 0

    m = Person(id=1, name="Bob", age=10)
    print(m)  # Person(id=1, name="Bob", age=10)

    """
    _class_primary_keys: Dict[str, type]
    _class_mutable: Set[str]
    _class_immutable: Set[str]

    _internal_id: UUID
    _state: ModelState
    _persistent_values: Dict[str, Any]
    _primary_keys: Tuple[Optional[T], ...]
    _listener: EventListener
    _initialized: bool

    def __init__(self):
        self.pre_setup_model()
        self.post_setup_model()

    def pre_setup_model(self):
        self._initialized = False
        self._internal_id = uuid4()
        self._persistent_values = {}
        self._listener = EventListener()

    def post_setup_model(self):
        self._state = ModelState.CLEAN
        self._primary_keys = self._get_primary_keys()
        self._initialized = True

    def _get_primary_keys(self) -> Tuple[Optional[T], ...]:
        return tuple([
            getattr(self, key)
            for key in self._class_primary_keys])

    def get_keys(self) -> Tuple[Optional[T], ...]:
        """
        Returns the internal tuple with the primary keys if the class.

        :return: The tuple with primary keys.
        """
        return self._primary_keys

    def _get_mutable_fields(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self._class_mutable}

    def get_children(
        self, recursive: bool = False, children: List[BaseModel] = None, top_level: Optional[BaseModel] = None
    ) -> List[BaseModel]:
        """
        Returns the list of all children of the current model. This algorithm checks in
        runtime for all objects refered by the instance, whether directly, through a list
        or a set. When `recursive` is True, then the algorithm will recursively search through
        all children. `children` and `top_level` are control variables that indicate which
        models have already been inspected by this function, in order to avoid infinite
        recursion if any circular dependency exists.

        :param recursive: If True, recursively searches for children. Returns only
                          first degree relationships otherwise. Defaults to False.
        :param children: List of existing models already inspected.
        :param top_level: The top-level model from where inspection started.
        :return: The list of all children.
        """

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

            # iterables are only supported if the values
            # are not iterables - there is no recursiveness
            if isinstance(value, Iterable):
                if isinstance(value, dict):
                    value = value.values()

                for item in value:
                    check(item)
            else:
                check(value)

        return children

    def _rollback(self):
        """
        Restore the persistent values in the model to their original attributes.
        """
        for attr, value in list(self._persistent_values.items()):
            setattr(self, attr, value)

        self._persistent_values = {}

    def _persist(self):
        """
        Persists the current attribute values by emptying the internal persistent
        dictionary. Once this is called, it is not possible to rollback to the
        old values anymore. It is recommended that this method should only be called
        by the party that persisted the values on the remote server.
        """
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

    # TODO: internal mutable fields (lists and sets) are not affected
    # by this interception, therefore the call to self._update will
    # not happen - we should figure out a way to trigger self._update
    # in those cases
    def __setattr__(self, name, value):
        if name in self._class_mutable:
            self._update(name, value)

        super().__setattr__(name, value)

        if name in self._class_primary_keys:
            self._primary_keys = self._get_primary_keys()
