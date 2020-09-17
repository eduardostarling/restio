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

        @address.setter
        def _validate_address(self, address: str):
            if not address:
                raise ValueError("Invalid address.")
            return address


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

Fields' default values are assigned to the model instance as soon as they are accessed for the first time, or right after the constructor returns.

Every :code:`Field` subtype should have its own default value, which can be configured by either using the keyword :code:`default` or :code:`default_factory`. :code:`default` accepts a static value, while :code:`default_factory` accepts callables.

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

No **restio** native field will automatically define a default value. Fields without default are always required, and failing to provide them will cause a failure after the constructor returns. The only exception applies to when fields are nullable (with :code:`allow_none=True`), in which case the default value is :code:`None` unless specified otherwise.


Constructor
^^^^^^^^^^^

By default, a model type will have a base constructor with arguments that match the field names. This means that for the model

.. code-block:: python

    class Person(BaseModel):
        name: StrField = StrField()
        age: IntField = IntField(default=18)

you can instantiate :code:`Person` by

.. code-block:: python

    person = Person(name="James Hetfield", age=57)

    person.name  # James Hetfield
    person.age   # 57

It would also be ok to not provide :code:`age` on the constructor, in which case the default value applies:

.. code-block:: python

    person = Person(name="James Hetfield")

    person.name  # James Hetfield
    person.age   # 18

Otherwise, fields are mandatory:

.. code-block:: python

    person = Person()  # error!

If you wish to disable or modify the default constructor behavior, you might either deactivate the initialization when defining the class (please see :ref:`model_meta` for details about :code:`class Meta`):

.. code-block:: python

    class Person(BaseModel):
        class Meta:
            init = False

        name: StrField = StrField()
        age: IntField = IntField(default=18)

or overwrite the constructor without calling the base constructor:

.. code-block:: python

    class Person(BaseModel):
        name: StrField = StrField()
        age: IntField = IntField(default=18)

        def __init__(self, name: str, age: int):
            self.name = name
            self.age = age + 10

It is even possible to have a custom constructor and benefit from the default behavior:

.. code-block:: python

    class Person(BaseModel):
        name: StrField = StrField()
        age: IntField = IntField(default=18)

        can_drink: bool

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.can_drink = self.age > 18


Fields can also be individually marked to not be initialized by providing :code:`init=False`, in which case the base constructor will ignore the parameter if it is provided. The field value after instantiating the model should either be the field default value or a custom value set by a manually implemented constructor.

.. code-block:: python

    class Person(BaseModel):
        name: StrField = StrField()
        age: IntField = IntField(default=18, init=False)

    person = Person(name="James Hetfield", age=57)
    person.age  # 18

Which is equivalent to

.. code-block:: python

    class Person(BaseModel):
        name: StrField = StrField()
        age: IntField = IntField(init=False)

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.age = 18

        person = Person(name="James Hetfield", age=57)
        person.age  # 18

Failing to assigning a value to a field before the instantiation finishes will result in an Exception.


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
        weight: IntField = IntField(default=0)

    model = Model()
    model.id      # None
    model.weight  # 0

    model.id = "some_value"  # ok
    model.id = 1             # error
    model.id                 # some_value

    model.weight = 65       # ok
    model.weight = "65 kg"  # error
    model.weight            # 65

    model_constructed = Model(id="value", weight=70)  # ok
    model_constructed.id                               # value
    model_constructed.weight                           # 70

    model_constructed = Model(id=1, weight=70)        # error


Setters and Properties
^^^^^^^^^^^^^^^^^^^^^^

All fields support custom assignment validation by either using the field decorator :code:`Field.setter` or by creating a custom property directly in the model.

**Setters**

The :code:`setter` decorator is more convenient because it doesn't require creating a custom :code:`getter`. For example, if you wish to validate that all :code:`Employees` are 18 or older at all times, this can be done as following:

.. code-block:: python

    from restio.model import BaseModel
    from restio.fields import StrField, IntField

    class Employee(BaseModel):
        name: StrField = StrField()
        age: IntField = IntField()

        @age.setter
        def _validate_age(self, age: int) -> int:
            if age < 18:
                raise ValueError(f"Employee {self.name} should be 18 or older.")
            return age


Or, if the validation function lives elsewhere, it is also possible to define it in the constructor of the field:

.. code-block:: python

    from restio.model import BaseModel
    from restio.fields import StrField, IntField

    def _validate_age(model: Employee, age: int) -> int:
        if age < 18:
            raise ValueError(f"Employee {model.name} should be 18 or older.")
        return age

    class Employee(BaseModel):
        name: StrField = StrField()
        age: IntField = IntField(setter=_validate_age)


The value returned by the :code:`setter` is ultimately the value assigned to the field, therefore you should always return the final value to be assigned. For validation only, that is normally the input value (as seen above).

Please keep in mind that:

- The type-checking is always done before the setter is called, and **there is no type-checking** for the value returned by the :code:`setter`.
- Default values are also checked by the :code:`setter`.

**Properties**

If you wish an even more customized behavior, Models and Fields will support the built-in python decorator :code:`@property`. Let's say that, in the last example, there might be some :code:`Employees` that were forcefully registered in the remote data store with an age of 16 by a database administrator, but the restriction of hiring Employees older than 18 through the API still applies. In that case, we should be able to bypass the data assignment for the very young Employees:

.. code-block:: python

    from restio.model import BaseModel
    from restio.fields import StrField, IntField

    class Employee(BaseModel):
        name: StrField = StrField()
        _age: IntField = IntField()

        @property
        def age(self) -> int:
            return self._age

        @age.setter
        def age(self, value: int):
            if value < 18:
                raise ValueError(f"Employee {self.name} should be 18 or older.")
            self._age = value

    employee = Employee(name="John", age=18)

    employee.age = 15   # fails
    employee._age = 15  # succeeds


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

    class Company(BaseModel):
        address: StrField = StrField(default="The Netherlands")
        employees: FrozenSetModelField[Employee] = FrozenSetModelField(Employee, default_factory=frozenset)

    employee = Employee(name="Jay Pritchett")

    company = Company()
    company.employees = frozenset({employee})


The effect of using a relational field is that during a Transaction commit **restio** will check for the relationship between models by calling :code:`BaseModel.get_children()`, and trigger DAO tasks according to the dependency trees formed by all models in cache. For the example above, running :code:`company.get_children()` will return a list containing a single object :code:`employee`.

There are currently three types of :code:`ModelField` provided natively by **restio**: :code:`ModelField`, :code:`TupleModelField` and :code:`FrozenSetModelField`.

Please note that it is not possible to create a relationship between models that are not yet registered in the :ref:`transaction` cache, so that **restio** can properly track changes on the dependencies. For instance, if you wish to add the :code:`company` above to the Transaction cache, then :code:`employee` should be registered first.


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
        key: StrField = StrField(pk=True, frozen=FrozenType.UPDATE)

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

.. _model_meta:

Model Meta
----------

All model classes contain an internal structure :code:`ModelMeta`, which defines the behavior of the model in runtime. Some :code:`ModelMeta` attributes can be overwritten by declaring the model with a nested class :code:`Meta`:

.. code-block:: python

    class Model(BaseModel):
        class Meta:
            pass

        ...

The individual attributes given to :code:`Meta` are always static and accumulate through inheritance.

Currently, the following attributes can be provided to :code:`Meta`:

- :code:`init` (:code:`bool`, defaults to :code:`True`): Indicates if the default base constructor behavior will be active. When :code:`True`, parameters given to the constructor will be assigned to fields that match their names. When :code:`False`, this assignment is skipped.
- :code:`init_ignore_extra` (:code:`bool`, defaults to :code:`True`): Indicates if extra parameters given to the constructor will be ignored. When not ignored, any extra parameter passed to :code:`BaseModel.__init__` raises an Exception.


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

        @address.setter
        def _validate_address(self, address: str) -> str:
            if not address:
                raise ValueError("Invalid address.")
            return address


    class Company(BaseModel):
        name: StrField = StrField(pk=True, frozen=FrozenType.UPDATE)
        employees: FrozenSetModelField[Employee] = FrozenSetModelField(Employee)

        def hire_employee(self, employee: Employee):
            # frozensets are immutable, therefore we need to re-set the value back to the
            # model
            self.employees = frozenset(self.employees.union({employee}))

        @employees.setter
        def _validate_employee(self, employees: FrozenSet[Employee]) -> FrozenSet[Employee]:
            for employee in employees:
                if not employee.age >= 18:
                    raise ValueError(f"The employee {employee.name} is not 18 yet.")

            return employees


    # it is now easy to manipulate objects in the application
    employee_a = Employee(name="Alice", age=27)
    employee_b = Employee(name="Bob", age=19)

    company = Company(name="Awesome Company", employees=frozenset({employee_a}))  # this works

    employee_c = Employee(name="Junior", age=16)
    company.hire_employee(employee_c)  # this fails

