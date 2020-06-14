.. _transaction:

Transaction
===========

A **restio** :code:`Transaction` coordinates the context of persistent operations to a remote REST API.

Transactions benefit from the relationship between **Data Access Objects** and **Models** to decide how data should be persisted on the remote server by tracking how changes were made to models.

A **DAO** :code:`EmployeeDAO` can be mapped to a **Model** :code:`Employee` in a Transaction by running :code:`Transaction.register_dao`:

.. seealso::
    You can find the implementation of :code:`Employee` and :code:`EmployeeDAO` in :ref:`dao`:

.. code-block:: python

    from restio.transaction import Transaction

    from myproject.models import Employee
    from myproject.dao import EmployeeDAO

    transaction = Transaction()

    # informs the transaction about the relationship between EmployeeDAO and Employee
    transaction.register_dao(EmployeeDAO(Employee))


A transaction instance is supposed to resemble a database transaction, but used within the context of REST APIs. With this module, we try to solve common problems faced when using a REST API, such as caching, persistency, state management and performance.

For example, we can use the transaction to retrieve an :code:`Employee` from the remote server:

.. code-block:: python

    employee = await transaction.get(Employee, 1)  # Employee with primary key 1

    print(employee)  # Employee(key=1, name="John Doe", age=30, address="The Netherlands")
    print(id(employee))  # 123456


Trying to retrieve the same employee will not result in a new call to the server, and instead will bring the object from the Transaction cache:

.. code-block:: python

    employee = await transaction.get(Employee, 1)

    print(employee)  # Employee(key=1, name="John Doe", age=30, address="The Netherlands")
    print(id(employee))  # 123456

    employee_again = await transaction.get(Employee, 1)  # same employee

    print(employee_again)  # Employee(key=1, name="John Doe", age=30, address="The Netherlands")
    print(id(employee_again))  # 123456


.. note::
    Please visit :ref:`strategies` for more information about caching.

Differently from a normal relational database, a generic REST API should be stateless and doesn't implement transactions. Therefore, *it is never guaranteed that the transaction is atomic when interacting with the remote server*. However, replicating the remote models as local abstractions within the :code:`Transaction` module allows the framework to anticipate common issues, such as model relationship inconsistencies or bad data.

Going back to the example shown in :ref:`dao`, let's now use the :code:`Transaction` to add a new :code:`Employee` Jay to the remote API, and at the same time to update the address of *John*:

.. code-block:: python

    ...

    transaction = Transaction()
    transaction.register_dao(EmployeeDAO(Employee))

    # retrieves John Doe's model
    john = await transaction.get(Employee, 1)
    john.address = "Brazil"

    # create a new employee Jay Pritchett locally
    jay = Employee(name="Jay Pritchett", age=65, address="California")
    # tells the transaction to add the new employee to its context
    transaction.add(jay)


If you don't want to call :code:`register_dao` for every new :code:`Transaction` instance you create, you can extend :code:`Transaction` in order to get this done automatically:

.. code-block:: python

    from restio.transaction import Transaction

    from myproject.models import Employee
    from myproject.dao import EmployeeDAO

    ...

    class MyTransaction(Transaction):
        def __init__(self) -> None:
            super().__init__()

            self.register_dao(EmployeeDAO(Employee))

    ...

At this point, no operation has been done to the remote server *yet*. It is necessary to tell the :code:`Transaction` to :code:`commit` its changes explicitly.


Commit
------

.. code-block:: python

    transaction = MyTransaction()
    ...

    await transaction.commit()


The :code:`commit` method will inspect all models stored on the transaction's internal cache and verify which models should be modified. In the example above, right before the commit *John* has state :code:`DIRTY` (because it has been modified) and *Jay* has state :code:`NEW` (because it still has to be added):

.. code-block:: python

    ...

    transaction = MyTransaction()

    # retrieves John Doe's model
    john = await transaction.get(Employee, 1)
    john.address = "Brazil"

    # create a new employee Jay Pritchett locally
    jay = Employee(name="Jay Pritchett", age=65, address="California")
    # tells the transaction to add the new employee to its context
    transaction.add(jay)

    # this is where the actual changes happen - Jay will be
    # created and John will be updated
    await transaction.commit()


Its is not up to the developer anymore to figure out in which order the operations need to be persisted on the remote server, and which models are unchanged. The transaction will take care of drawing the graph of dependencies between models and trigger all requests to the remote REST API in an optimal way.


Persistency Strategy
--------------------

Transactions by default are instantiated with :code:`strategy=PersistentStrategy.INTERRUPT_ON_ERROR`. When an error occurs during a :code:`commit`, the value of :code:`strategy` will dictate the behavior:

- :code:`INTERRUPT_ON_ERROR` will cause the commit to interrupt the scheduling of new **DAO Tasks** and will wait until all current **DAO Tasks** finalize.
- :code:`CONTINUE_ON_ERROR` will cause the commit to ignore the error and continue scheduling all available **DAO Tasks** until all models are processed.


DAO Tasks
^^^^^^^^^

**DAO Tasks** will store the result of the calls to the DAOs during a :code:`commit`, those being to either :code:`add`, :code:`update` or :code:`remove`. If anything goes wrong in one of those methods, then it is possible to revisit the results of all tasks performed by the :code:`commit`:

.. code-block:: python

    from restio.dao import DAOTask

    ...

    tasks = await transaction.commit()

    dao_task: DAOTask
    for dao_task in tasks:
        try:
            # obtains the value returned by the DAO function, if any
            result = await dao_task
        except Exception:
            # if something went wrong during the commit, then it is time
            # to treat it - below, we just print the stack trace to the
            # terminal
            dao_task.task.print_stack()


Rollback
--------

.. code-block:: python

    transaction = MyTransaction()
    ...

    transaction.rollback()

Because the operations on server-side are done in multiple HTTP requests, it is not possible to guarantee atomicity between requests. Therefore, :code:`Transaction.rollback` will only revert the local changes that have not yet been persisted.

Rollbacks are useful when the cache is populated with a lot of data.
