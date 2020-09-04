from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable, Dict, List, Optional, Type
from uuid import UUID, uuid4

from restio.event import EventListener
from restio.fields.base import Field, T_co
from restio.state import ModelState


def _check_model_type(obj: Optional[BaseModel]):
    if not isinstance(obj, BaseModel):
        raise TypeError("The provided object is not of type BaseModel.")


class ModelMeta:
    fields: Dict[str, Field]
    primary_keys: Dict[str, Field]

    def __init__(self):
        self.fields = dict()
        self.primary_keys = dict()


class BaseModelMeta(type):
    """
    BaseModel metaclass. Responsible to internally cache the data schema in a BaseModel
    subclass by identifying fields and primary keys.
    """

    def __new__(cls, name: str, bases: Iterable[Type[BaseModel]], dct: Dict[str, Any]):
        meta: ModelMeta = ModelMeta()
        dct["_meta"] = meta

        # other internal fields not initialized in BaseModel
        dct["_internal_id"] = None
        dct["_listener"] = None
        dct["_persistent_values"] = None

        model_class: BaseModel = super().__new__(cls, name, bases, dct)  # type: ignore

        base: Type[BaseModel]
        for base in bases:
            try:
                meta.fields.update(base._meta.fields)
                meta.primary_keys.update(base._meta.primary_keys)
            except Exception:
                pass

        # process class fields
        for field_name, field_value in dct.items():
            if not isinstance(field_value, Field):
                continue

            model_class._meta.fields[field_name] = field_value
            if field_value.pk:
                model_class._meta.primary_keys[field_name] = field_value

        return model_class

    def __call__(self, *args, **kwargs):
        instance: BaseModel = super().__call__(*args, **kwargs)

        # stores the default after the constructor, if nothing has been set yet
        for field in instance._meta.fields.values():
            field._store_default(instance, force=False)

        instance._internal_id = uuid4()
        instance._persistent_values = {}
        instance._listener = EventListener()
        instance._initialized = True

        return instance


MODEL_PRE_UPDATE_EVENT = "__pre_update__"
MODEL_UPDATE_EVENT = "__updated__"


class BaseModel(metaclass=BaseModelMeta):
    """
    A representation of a remote object model in a Transaction object.

    BaseModel is an abstract class that should be extended to represent models incoming
    from or outgoing to a remote REST API.

    Models can exist independently from Transactions but contain an internal state that
    indicates the status of the model within the current context. The Transactions are
    responsible to control this state. Also, each model contains a set of control
    attributes that indicate which fields are watched by restio internals. By default,
    all Field descriptors in the model will become field attributes. Fields declared
    with pk=True will be used by restio to optimize the caching of the models in a
    Transaction.

    Models that change over time will contain an internal dictionary with the latest
    know persistent value of each field. This is done to guarantee fast rollback of the
    values when the Transaction is invalid, and to also indicate which values might
    have changed within the transaction scope. If a field is modified directly, the
    model will intercept the change and save the older value into the persistent
    dictionary until `_persist` is called. During a `_rollback` call, however, the
    stored values are re-assigned to their original attributes. Each attribute change
    will also dispatch an update event so that the transaction is aware of changes and
    manages the model's internal state accordingly. The persistent dictionary (through
    the helper method `is_field_modified`) can also be used by DAO's to verify which
    values where updated prior to sending a request through the REST API, thus allowing
    for proper optimization and minimizing chances of conflicting changes on the remote
    object.

    All models automatically generate a random internal UUID when created. This UUID is
    used internally for comparison purposes, and externally as an identity. Although
    this attribute is not explicitly set as private, it should never be modified.
    """

    # these are all initialized by the metaclass
    _meta: ModelMeta

    __state: ModelState = ModelState.UNBOUND
    __primary_keys: Optional[Dict[str, T_co]] = None
    _initialized: bool = False

    _internal_id: UUID
    _persistent_values: Dict[str, Any]
    _listener: EventListener

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
        children: Optional[List[BaseModel]] = None,
        top_level: Optional[BaseModel] = None,
    ) -> List[BaseModel]:
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
            children = []

        if top_level:
            if self == top_level:
                return children

            if self not in children:
                children.append(self)
        else:
            top_level = self

        for value in self.dependency_fields.values():

            def check(child: Optional[BaseModel]):
                # this can happen when the field allows none
                if not child:
                    return

                if child not in children:  # type: ignore
                    if recursive:
                        child.get_children(recursive, children, top_level)
                    else:
                        children.append(child)

            # iterables are only supported if the values
            # are not iterables - there is no recursiveness
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

        name: str = field.name
        if name in self._persistent_values:
            if value == self._persistent_values[name]:
                del self._persistent_values[name]
        else:
            mutable_fields = self.fields
            if value != mutable_fields[name]:
                self._persistent_values[name] = mutable_fields[name]

        self._listener.dispatch(MODEL_UPDATE_EVENT, self)

    def __eq__(self, other: BaseModel) -> bool:
        if other and isinstance(other, type(self)):
            return self._internal_id == other._internal_id

        return False

    def __hash__(self):
        return hash(str(self._internal_id))
