from __future__ import annotations

from collections.abc import Iterable
from reprlib import Repr
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Set, Tuple, Type
from uuid import UUID, uuid4

from restio.event import EventListener
from restio.fields.base import Field, T_co
from restio.shared import (
    CURRENT_SESSION,
    MODEL_INSTANTIATED_EVENT,
    MODEL_PRE_UPDATE_EVENT,
    MODEL_TYPE_REGISTRY,
    MODEL_UPDATE_EVENT,
)
from restio.state import ModelState

if TYPE_CHECKING:
    from restio.session import Session


def _check_model_type(obj: Optional[BaseModel]):
    if not isinstance(obj, BaseModel):
        raise TypeError("The provided object is not of type BaseModel.")


class ModelMeta:
    __slots__ = ("init", "init_ignore_extra", "repr", "fields", "primary_keys", "alias")

    init: bool
    init_ignore_extra: bool
    repr: bool
    fields: Dict[str, Field]
    primary_keys: Dict[str, Field]
    alias: Optional[str]

    def __init__(self):
        self.init = True
        self.init_ignore_extra = True
        self.repr = True
        self.fields = dict()
        self.primary_keys = dict()
        self.alias = None


# Meta attributes that don't get inherited from parent classes
__MODEL_META_NOT_INHERITED__ = ("alias",)
# Read-only meta attributes, can't be modified by model class
__MODEL_META_READONLY__ = ("fields", "primary_keys")


class BaseModelMeta(type):
    __slots__ = ()

    """
    BaseModel metaclass. Responsible to internally cache the data schema in a BaseModel
    subclass by identifying fields and primary keys.
    """

    def __new__(cls, name: str, bases: Tuple[Type, ...], dct: Dict[str, Any]):
        # internal fields not initialized in BaseModel
        dct["_internal_id"] = None
        dct["_hash"] = None
        dct["_listener"] = None
        dct["_persistent_values"] = None

        # prepares metadata for the model type
        meta = ModelMeta()
        dct["_meta"] = meta

        def _update_meta(
            _meta: Optional[ModelMeta],
            extend: bool,
            not_inherited: Tuple[str, ...] = tuple(),
        ):
            if not _meta:
                return

            propagate_meta = (
                set(meta.__slots__) - set(__MODEL_META_READONLY__) - set(not_inherited)
            )

            for meta_attribute in propagate_meta:
                if not hasattr(_meta, meta_attribute):
                    continue

                setattr(meta, meta_attribute, getattr(_meta, meta_attribute))

            # excluded meta, needs to be propagated manually
            if extend:
                meta.fields.update(_meta.fields)
                meta.primary_keys.update(_meta.primary_keys)

        base: Type[BaseModel]
        for base in bases:
            if not hasattr(base, "_meta"):
                continue

            _update_meta(base._meta, True, __MODEL_META_NOT_INHERITED__)

        _update_meta(dct.get("Meta", None), False)

        # process class fields
        for field_name, field_value in dct.items():
            if not isinstance(field_value, Field):
                continue

            meta.fields[field_name] = field_value
            if field_value.pk:
                meta.primary_keys[field_name] = field_value

        # set alias name to class name when None
        name_alias = meta.alias or name

        # validate if the alias is not duplicate
        # the caveat here is that two classes with the same name in two
        # different files will have a name collision and fail initializing
        if name_alias in MODEL_TYPE_REGISTRY:
            raise ValueError(
                f"Model alias `{name_alias}` is already used by another class."
            )

        cls_object = super().__new__(cls, name, bases, dct)

        # set the model alias to the model type
        if name_alias != "BaseModel":
            MODEL_TYPE_REGISTRY[name_alias] = cls_object

        return cls_object

    def __call__(self, *args, **kwargs):
        instance: BaseModel = super().__call__(*args, **kwargs)

        # stores the default after the constructor, if nothing has been set yet
        # this is implemented here so that this is always called, regardless of the
        # models with custom constructors calling or not super().__init__()
        for field in instance._meta.fields.values():
            field._store_default(instance, force=False)

        instance._internal_id = uuid4()
        instance._hash = hash((instance.__class__, str(instance._internal_id)))
        instance._persistent_values = {}
        instance._listener = EventListener()
        instance._initialized = True

        session = CURRENT_SESSION.get()
        if session:
            session._listener.dispatch(MODEL_INSTANTIATED_EVENT, instance)

        return instance


_repr_obj: Repr = Repr()
_repr_obj.maxother = 200


class BaseModel(metaclass=BaseModelMeta):
    """
    A representation of a remote object model.

    BaseModel is an abstract class that should be extended to represent models incoming
    from or outgoing to a remote REST API.

    Models can exist independently from Sessions but contain an internal state that
    indicates the status of the model within the current context. The Sessions are
    responsible to control this state. Also, each model contains a set of control
    attributes that indicate which fields are watched by restio internals. By default,
    all Field descriptors in the model will become field attributes. Fields declared
    with pk=True will be used by restio to optimize the caching of the models in a
    Session.

    Models that change over time will contain an internal dictionary with the latest
    know persistent value of each field. This is done to guarantee fast rollback of the
    values when the Session is invalid, and to also indicate which values might have
    changed within the session scope. If a field is modified directly, the model will
    intercept the change and save the older value into the persistent dictionary until
    `_persist` is called. During a `_rollback` call, however, the stored values are
    re-assigned to their original attributes. Each attribute change will also dispatch
    an update event so that the session is aware of changes and manages the model's
    internal state accordingly. The persistent dictionary (through the helper method
    `is_field_modified`) can also be used by DAO's to verify which values where updated
    prior to sending a request through the REST API, thus allowing for proper
    optimization and minimizing chances of conflicting changes on the remote object.

    All models automatically generate a random internal UUID when created. This UUID is
    used internally for comparison purposes, and externally as an identity. Although
    this attribute is not explicitly set as private, it should never be modified.
    """

    # these are all initialized by the metaclass
    _meta: ModelMeta

    __state: ModelState = ModelState.UNBOUND
    __primary_keys: Optional[Dict[str, Any]] = None
    _initialized: bool = False

    _internal_id: UUID
    _hash: int
    _persistent_values: Dict[str, Any]
    _listener: EventListener

    def __init__(self, **kwargs: T_co):
        """
        Instantiates the model by matching `kwargs` parameters to field names.
        Behavior is disabled when init=False in the model Meta class.

        :param kwargs: The dictionary of keyword arguments matching the field names of
                       the model class.
        :raises ValueError: When invalid arguments are provided.
        """
        meta = self._meta

        if not meta.init:
            return

        for arg_name, value in kwargs.items():
            field_object = meta.fields.get(arg_name, None)

            if not field_object:
                if not meta.init_ignore_extra:
                    raise ValueError(
                        "Invalid argument provided to constructor of"
                        f" `{self.__class__.__name__}`: {arg_name}"
                    )
                continue  # pragma: no cover

            if not field_object.init:
                if not meta.init_ignore_extra:
                    raise ValueError(f"Attribute `{arg_name}` cannot be initialized.")
                continue  # pragma: no cover

            field_object.__set__(self, value)

    @property
    def _state(self) -> ModelState:
        """
        Returns the state of the current model.

        :return: The ModelState representation.
        """
        return self.__state

    @_state.setter
    def _state(self, state: ModelState):
        self.__state = state

    @property
    def primary_keys(self) -> Dict[str, T_co]:
        """
        Returns a dictionary containing all primary keys. The keys will be
        ordered in the same order as they are declared in the model type,
        also following the order in which they appear in class inheritance.

        This property is optimized to minimize the number of iterations done
        in the model instance by internalizing a cache with the latest retrieved
        primary keys. This cache is reset for every modification of a primary
        key and recovered during the next call to the property.

        :return: The ordered tuple of values.
        """
        if self.__primary_keys is None:
            self.__primary_keys = self._load_primary_keys()

        return self.__primary_keys

    def _load_primary_keys(self) -> Dict[str, T_co]:
        """
        Returns a dictionary containing the primary key fields (keys) and their
        current values in the model (values). This operation will inspect the
        instance and collect all current values on-spot.

        :return: Dictionary of primary keys values.
        """
        return {key: getattr(self, key) for key in self._meta.primary_keys}

    def _reset_primary_keys(self):
        """
        Resets the internal cache of primary keys for the instance.
        """
        self.__primary_keys = None

    def get_children(
        self,
        recursive: bool = False,
        children: Optional[Set[BaseModel]] = None,
        top_level: Optional[BaseModel] = None,
    ) -> Set[BaseModel]:
        """
        Returns the list of all children of the current model. This algorithm checks in
        runtime for all objects refered by the instance and that are part of fields
        marked with depends_on=True. When `recursive` is True, then the algorithm will
        recursively search through all children.

        `children` and `top_level` are control variables that indicate which models
        have already been inspected by this function, in order to avoid infinite
        recursion if any circular dependency exists. In most cases, they should be left
        empty.

        :param recursive: If True, recursively searches for children. Returns only
                          first degree relationships otherwise. Defaults to False.
        :param children: List of existing models already inspected.
        :param top_level: The top-level model from where inspection started.
        :return: The list of children.
        """

        if children is None:
            children = set()

        if top_level:
            if self == top_level:
                return children

            children.add(self)
        else:
            top_level = self

        for value in self.dependency_fields.values():

            def check(child: Optional[BaseModel]):
                # this can happen when the field allows none
                if not child or child in children:  # type: ignore
                    return

                if recursive:
                    child.get_children(recursive, children, top_level)
                else:
                    children.add(child)

            # iterables are only supported if the values are not iterables - there is
            # no recursiveness
            if isinstance(value, Iterable):
                value: Iterable[Any]
                for item in value:
                    check(item)
            else:
                check(value)

        return children

    @property
    def fields(self) -> Dict[str, Any]:
        """
        Returns the values of each field in the model instance.

        :return: A dict with keys containing the string names of the fields,
                 and values containing the value of the corresponding field.
        """
        return {k: getattr(self, k) for k in self._filter_fields(lambda v: True)}

    @property
    def dependency_fields(self) -> Dict[str, Any]:
        """
        Returns the values of each field that have relationship with other models.

        :return: The dictionary of fields and their values
        """
        return {
            k: getattr(self, k) for k in self._filter_fields(lambda v: v.depends_on)
        }

    def is_field_modified(self, field_name: str) -> bool:
        """
        Indicates of field with name `field_name` has been modified.

        :param field_name: The name of the field.
        :raises ValueError: When the field name does not exist.
        :return: True if field is modified, False otherwise.
        """
        if field_name not in self._meta.fields:
            raise ValueError(
                f"Field `{field_name}` does not exist in model"
                " `{self.__class__.__name__}`."
            )

        return field_name in self._persistent_values

    def _filter_fields(self, filt: Callable[[Field], bool]):
        return {k: v for k, v in self._meta.fields.items() if filt(v)}

    def _rollback(self):
        """
        Restore the persistent values in the model to their original attributes.
        """
        for attr, value in list(self._persistent_values.items()):
            setattr(self, attr, value)

        self._persist()

    def _persist(self):
        """
        Persists the current attribute values by emptying the internal persistent
        dictionary. Once this is called, it is not possible to rollback to the old
        values anymore. It is recommended that this method should only be called by the
        party that persisted the values on the remote server.
        """
        self._persistent_values = {}

    def _pre_update(self, field: Field[T_co], value: T_co):
        self._listener.dispatch(MODEL_PRE_UPDATE_EVENT, self, field, value)

    def _update(self, field: Field[T_co], value: T_co):
        if field.pk:
            self._reset_primary_keys()

        self._listener.dispatch(MODEL_UPDATE_EVENT, self, field, value)

    def _update_persistent_values(self, field: Field[T_co], value: T_co):
        name: str = field.name
        if name in self._persistent_values:
            if value == self._persistent_values[name]:
                del self._persistent_values[name]
        else:
            mutable_fields = self.fields
            if value != mutable_fields[name]:
                self._persistent_values[name] = mutable_fields[name]

    def __eq__(self, other: BaseModel) -> bool:
        return isinstance(other, self.__class__) and self._hash == other._hash

    def __repr__(self) -> str:
        if not self._meta.repr:
            return super().__repr__()

        def get_field_repr(field: str):
            value = getattr(self, field)
            return f"{field}={_repr_obj.repr(value)}"

        repr_args: List[str] = [
            get_field_repr(n) for n in self._filter_fields(lambda x: x.repr)
        ]
        return f"{self.__class__.__name__}({', '.join(repr_args)})"

    def __hash__(self) -> int:
        return self._hash
