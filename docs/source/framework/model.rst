.. _model:

Model
=====

A **restio** Model is a representation of a data model in a remote API.

For example, a model :code:`Employee` could be written using as following to represent an Employee stored in a remote REST API:

.. code-block:: python

    from typing import Optional

    from restio.fields import IntField, StrField, FrozenType
    from restio.model import BaseModel

    class Employee(BaseModel):
        key: IntField = IntField(pk=True, allow_none=True, frozen=FrozenType.ALWAYS)
        name: StrField = StrField()
        age: IntField = IntField(default=18)
        address: StrField = StrField(default="Company Address")

        def __init__(
            self,
            *,
            name: str,
            age: Optional[int] = None,
            address: Optional[str] = None
        ) -> None:
            self.name = name
            self.age = age or self.age  # uses default

            self.change_address(address or self.address)  # uses default

        def change_address(self, new_address: str):
            if not new_address:
                raise ValueError("Invalid address.")
            self.address = new_address


All **restio** models should inherit from :code:`restio.model.BaseModel`, and all fields should be of type :code:`restio.fields.Field`. :code:`BaseModel` will guarante that the models can be properly operated by the other **restio** modules, such as Transactions and Data Access Objects.

.. _fields:

Fields
------

All model attributes should be declared as fields. Fields tell **restio** how to track changes in models. They provide some additional functionality such as runtime type-checking, definition of primary keys, definition of defaults, frozen attributes, etc, and are fully configurable.

**restio** provides the following fields out-of-the-box.

- IntField
- StrField
- BoolField
- TupleField
- FrozenSetField
- ModelField
- TupleModelField
- FrozenSetModelField


Default values
^^^^^^^^^^^^^^

Field's default values are assigned to the model instance as soon as they are accessed for the first time, or right after the constructor returns.

Every Field subtype should have its own default value, which can be configured by either using the keyword :code:`default` or :code:`default_factory`. :code:`default` accepts a static value, while :code:`default_factory` accepts callables.

Example:

.. code-block:: python

    import random

    from restio.model import BaseModel
    from restio.fields import IntField

    class Model(BaseModel):
        static_default_field: IntField = IntField(default=25)
        factory_default_field: IntField = IntField(int, default_factory=lambda: random.randrange(10))

    model = Model()
    model.static_default_field   # 25
    model.factory_default_field  # 7

    another_model = Model()
    another_model.static_default_field   # 25
    another_model.factory_default_field  # 2

Most **restio** native fields will automatically set a :code:`default_factory` function to the field if nothing is provided. For example, the :code:`default_factory` for :code:`IntField()` will internally become :code:`int`, for :code:`StrField()` it will be :code:`str`, etc. This doesn't apply when :code:`allow_none` is :code:`True`, in which case the field's :code:`default_factory` will remain empty while its :code:`default` will be set to :code:`None`.

If you wish to force the input to be provided for a particular non-nullable field, then you should implement a constructor :code:`__init__` to the model class.

.. code-block:: python

    from restio.model import BaseModel
    from restio.fields import IntField

    class Model(BaseModel):
        val: IntField = IntField()

        def __init__(self, val: int) -> None:
            self.val = val


Runtime type-checking
^^^^^^^^^^^^^^^^^^^^^

Runtime type-checking is done during value assignment.

The base type :code:`Field` accepts the type parameter :code:`type_` in its contructor, and this is used for data validation. All pre-defined types from **restio** already provide this by default (e.g. :code:`IntField` is constructed with :code:`type_=int`, :code:`StrField` with :code:`type_=str`, etc).

A :code:`ContainerField` subtype will also check for the types of the objects stored in the container. For example, a :code:`TupleField(sub_type=str)` (or simply :code:`TupleField(str)`) will only accept tuples in which all values are of the type :code:`str`.

Most fields will not accept :code:`None` unless explicitly defined with :code:`allow_none=True`.

Example:

.. code-block:: python

    from typing import Optional

    from restio.model import BaseModel
    from restio.fields import StrField, IntField

    class Model(BaseModel):
        id: StrField = StrField(allow_none=True)
        weight: IntField = IntField()

        def __init__(self, id_: Optional[str] = None, weight: Optional[int] = None) -> None:
            # assigns default if nothing is provided
            self.id = id_ or self.id
            self.weight = weight or self.weight

    model = Model()
    model.id      # None
    model.weight  # 0

    model.id = "some_value"  # ok
    model.id = 1             # error
    model.id                 # some_value

    model.weight = 65       # ok
    model.weight = "65 kg"  # error
    model.weight            # 65

    model_constructed = Model(id_="value", weight=70)  # ok
    model_constructed.id                               # value
    model_constructed.weight                           # 70

    model_constructed = Model(id_=1, weight=70)        # error

.. _primary_keys:

Primary keys
^^^^^^^^^^^^

Primary keys are used to define Model uniqueness in the Transaction cache. At all times, there can only be a single model containing a particular primary key in the cache. Please check :ref:`strategies` for more in-depth details of the caching mechanism.

To define a primary key field in the model, use :code:`pk=True`.

Example:

.. code-block:: python

    from restio.model import BaseModel
    from restio.fields import StrField, IntField

    class Model(BaseModel):
        id: IntField = IntField(pk=True, allow_none=True)
        name: StrField = StrField()


You can define a composite primary key for any model type by specifying multiple :code:`pk` fields within the same class. The order in which they are evaluated is important and is the same in which the fields are declared. This also applies to inheritance.

Iterable fields cannot be primary keys. Typically, the field types below will be used as primary keys:

- IntField
- StrField


Relational fields
^^^^^^^^^^^^^^^^^

Fields can also contain relationships with other models types. It is possible to replicate the relational behavior existing on the server side using a :code:`ModelField`. :code:`ModelField` acts similarly as a foreign key in a relational database because it is defined with :code:`depends_on=True`.

Example:

.. code-block:: python

    from restio.model import BaseModel
    from restio.fields import StrField, IntField, FrozenSetModelField

    class Employee(BaseModel):
        id: IntField = IntField(pk=True, allow_none=True)
        name: StrField = StrField()

        def __init__(self, name: str) -> None:
            self.name = name

    class Company(BaseModel):
        address: StrField = StrField(default="The Netherlands")
        employees: FrozenSetModelField[Employee] = FrozenSetModelField(Employee)

    employee = Employee(name="Jay Pritchett")

    company = Company()
    company.employees = frozenset({employee})


The effect of using a relational field is that during a Transaction commit **restio** will check for the relationship between models by calling :code:`BaseModel.get_children()`, and trigger DAO tasks according to the dependency trees formed by all models in cache. For the example above, running :code:`company.get_children()` will return a list containing a single object :code:`employee`.

There are currently three types of :code:`ModelField` provided natively by **restio**: :code:`ModelField`, :code:`TupleModelField` and :code:`FrozenSetModelField`.


Frozen fields
^^^^^^^^^^^^^

Fields might have different behavior according to the lifecycle of the models. Some fields might be always read-only, others can be only defined during the creation of the remote model, and others can only be modified after the model has been created.

The behavior of each field can be controlled by using one of the keyword argument :code:`frozen` following the conventions:

- :code:`frozen=FrozenType.NONE` (default): the field is fully writable, and can be always modified.
- :code:`frozen=FrozenType.ALWAYS`: the field is fully read-only, and can never be modified.
- :code:`frozen=FrozenType.UPDATE`: the field is writable during creation, and read-only for updates (frozen for updated).
- :code:`frozen=FrozenType.CREATE`: the field is read-only during creation, and writable for updates (frozen for creation).

For example, frozen behavior is very useful for primary keys that should be defined by the client, but cannot change after creation:

.. code-block:: python

    from restio.model import BaseModel
    from restio.fields import StrField
    from restio.transaction import Transaction

    class Employee(BaseModel):
        # setting default_factory=None will make it mandatory to provide a
        # value before the constructor is finished
        key: StrField = StrField(pk=True, default_factory=None, frozen=FrozenType.UPDATE)

        def __init__(self, key: str):
            # assign the value in the constructor
            self.key = key

    transaction = Transaction()
    ...  # boiler-plate code, assign DAOs, etc

    # it is mandatory to instantiate the employee with a key
    employee = Employee(key="my_employee_key")

    transaction.add(employee)       # ok! model instance is now bound to the transaction
    await transaction.commit()      # Employee is created on the remote server

    employee.key = "something_else" # error, field is frozen for updates

The lifecycle of a model instance is controlled by :ref:`transaction`, therefore the check for non-authorized modification is only done when the instance is bound to a :code:`Transaction`. This check is disabled temporarily during a :code:`Transaction.get` or :code:`Transaction.commit` (otherwise, we wouldn't be able to update the instance with informating incoming from the server).

Fields might also be only server-side defined, and cannot change at all:

.. code-block:: python

    from restio.model import BaseModel
    from restio.fields import StrField
    from restio.transaction import Transaction

    class Employee(BaseModel):
        # allow_none=True makes the default value of the field to be None
        key: StrField = StrField(pk=True, allow_none=True, frozen=FrozenType.ALWAYS)

    transaction = Transaction()
    ...

    # it is still possible to modify the key here, since the
    # instance is not yet bound to a transaction
    employee = Employee()
    employee.key = "setting_invalid_key"

    transaction.add(employee)       # error, key cannot be different than None (the default)

Even when the change happens after adding:

.. code-block:: python

    # lets keep the defaults in place
    another_employee = Employee()

    transaction.add(another_employee)  # ok! instance is now bound to the transaction
    another_employee.key = "some_key"  # error, key cannot be modified now

Or after getting:

.. code-block:: python

    # how about getting the value from the remote first?
    one_more_employee = await transaction.get(Employee, "key_value")
    one_more_employee.key  # key_value
    one_more_employee.key = "other_key"  # error, key cannot be modified


Example using relational models
-------------------------------

We can extend the example on the top of this page by implementing and extra `Company` model that contains a set of employees:

.. code-block:: python

    from typing import FrozenSet, Optional

    from restio.fields import FrozenSetModelField, FrozenType, IntField, StrField
    from restio.model import BaseModel


    class Employee(BaseModel):
        key: IntField = IntField(pk=True, allow_none=True, frozen=FrozenType.ALWAYS)
        name: StrField = StrField()
        age: IntField = IntField(default=18)
        address: StrField = StrField(default="Company Address")

        def __init__(
            self,
            *,
            name: str,
            age: Optional[int] = None,
            address: Optional[str] = None,
        ) -> None:
            self.name = name
            self.age = age or self.age  # uses default

            self.change_address(address or self.address)  # uses default

        def change_address(self, new_address: str):
            if not new_address:
                raise ValueError("Invalid address.")
            self.address = new_address


    class Company(BaseModel):
        name: StrField = StrField(pk=True, allow_none=False, frozen=FrozenType.UPDATE)
        employees: FrozenSetModelField[Employee] = FrozenSetModelField(Employee)

        def __init__(self, name: str, employees: FrozenSet[Employee]):
            self.name = name

            for employee in employees:
                self.hire_employee(employee)

        def hire_employee(self, employee: Employee):
            # frozensets are immutable, therefore we need to re-set the value
            # back to the model
            if not employee.age >= 18:
                raise ValueError(f"The employee {employee.name} is not 18 yet.")

            self.employees = frozenset(self.employees.union({employee}))


    # it is now easy to manipulate objects in the application
    employee_a = Employee(name="Alice", age=27)
    employee_b = Employee(name="Bob", age=19)

    company = Company(name="Awesome Company", employees=frozenset({employee_a}))  # this works

    employee_c = Employee(name="Junior", age=16)
    company.hire_employee(employee_c)  # this fails
