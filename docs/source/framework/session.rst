.. _session:

Session
=======

A **restio** :code:`Session` coordinates the context of persistent operations to a remote REST API.

Sessions benefit from the relationship between **Data Access Objects** and **Models** to decide how data should be persisted on the remote server by tracking how changes were made to models.

A **DAO** :code:`EmployeeDAO` can be mapped to a **Model** :code:`Employee` in a Session by running :code:`Session.register_dao`:

.. seealso::
    You can find the implementation of :code:`Employee` and :code:`EmployeeDAO` in :ref:`dao`:

.. code-block:: python

    from restio.session import Session

    from myproject.models import Employee
    from myproject.dao import EmployeeDAO

    session = Session()

    # informs the session about the relationship between EmployeeDAO and Employee
    session.register_dao(EmployeeDAO(Employee))


A session instance is supposed to resemble a database transaction, but used within the context of REST APIs. With this module, we try to solve common problems faced when using a REST API, such as caching, persistency, state management and performance.

For example, we can use the session to retrieve an :code:`Employee` from the remote server:

.. code-block:: python

    employee = await session.get(Employee, 1)  # Employee with primary key 1

    print(employee)  # Employee(key=1, name="John Doe", age=30, address="The Netherlands")
    print(id(employee))  # 123456


Trying to retrieve the same employee will not result in a new call to the server, and instead will bring the object from the Session cache:

.. code-block:: python

    employee = await session.get(Employee, 1)

    print(employee)  # Employee(key=1, name="John Doe", age=30, address="The Netherlands")
    print(id(employee))  # 123456

    employee_again = await session.get(Employee, 1)  # same employee

    print(employee_again)  # Employee(key=1, name="John Doe", age=30, address="The Netherlands")
    print(id(employee_again))  # 123456


.. note::
    Please visit :ref:`strategies` for more information about caching.

Differently from a normal relational database, a generic REST API should be stateless and in most cases it won't implement transactions. Therefore, *it is never guaranteed that the session will perform all actions atomicly when interacting with the remote server*. However, replicating the remote models as local abstractions within the :code:`Session` module allows the framework to anticipate common issues, such as model relationship inconsistencies or bad data, apart from keeping cache.

Going back to the example shown in :ref:`dao`, let's now use the :code:`Session` to add a new :code:`Employee` Jay to the remote API, and at the same time to update the address of *John*:

.. code-block:: python

    ...

    session = Session()
    session.register_dao(EmployeeDAO(Employee))

    # retrieves John Doe's model
    john = await session.get(Employee, 1)
    john.address = "Brazil"

    # create a new employee Jay Pritchett locally
    jay = Employee(name="Jay Pritchett", age=65, address="California")
    # tells the session to add the new employee to its context
    session.add(jay)


If you don't want to call :code:`register_dao` for every new :code:`Session` instance you create, you can extend :code:`Session` in order to get this done automatically:

.. code-block:: python

    from restio.session import Session

    from myproject.models import Employee
    from myproject.dao import EmployeeDAO

    ...

    class MySession(Session):
        def __init__(self) -> None:
            super().__init__()

            self.register_dao(EmployeeDAO(Employee))

    ...

At this point, no operation has been done to the remote server *yet*. It is necessary to tell the :code:`Session` to :code:`commit` its changes explicitly.


.. _session_commit:

Commit
------

.. code-block:: python

    session = MySession()
    ...

    await session.commit()


The :code:`commit` method will inspect all models stored on the session's internal cache and verify which models should be modified. In the example above, right before the commit, *John* has state :code:`DIRTY` (because it has been modified) and *Jay* has state :code:`NEW` (because it still has to be added):

.. code-block:: python

    ...

    session = MySession()

    # retrieves John Doe's model
    john = await session.get(Employee, 1)
    john.address = "Brazil"

    # create a new employee Jay Pritchett locally
    jay = Employee(name="Jay Pritchett", age=65, address="California")
    # tells the session to add the new employee to its context
    session.add(jay)

    # this is where the actual changes happen - Jay will be
    # created and John will be updated
    await session.commit()


Its is not up to the developer anymore to figure out in which order the operations need to be persisted on the remote server in runtime, and which models are unchanged. The session will take care of drawing the graph of dependencies between models and trigger all requests to the remote REST API in an optimal way.

By default, :code:`commit()` enables the flag :code:`raise_for_status=True`, which will make an extra call to :code:`Session.raise_for_status()` at the end of the commit.


Persistency Strategy
--------------------

Sessions by default are instantiated with :code:`strategy=PersistentStrategy.INTERRUPT_ON_ERROR`. When an error occurs during a :code:`commit`, the value of :code:`strategy` will dictate the behavior:

- :code:`INTERRUPT_ON_ERROR` will cause the commit to interrupt the scheduling of new **DAO Tasks** and will wait until all current **DAO Tasks** finalize.
- :code:`CONTINUE_ON_ERROR` will cause the commit to ignore the error and continue scheduling all available **DAO Tasks** until all models are processed.


DAO Tasks
^^^^^^^^^

**DAO Tasks** will store the result of the calls to the DAOs during a :code:`commit`, those being to either :code:`add`, :code:`update` or :code:`remove`. If anything goes wrong in one of those methods, then it is possible to revisit the results of all tasks performed by the :code:`commit` manually:

.. code-block:: python

    from restio.dao import DAOTask

    ...

    tasks = await session.commit()

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

It is also possible to raise a :code:`SessionException` when at least one DAOTask has thrown an exception:

.. code-block:: python

    session.raise_for_status(tasks)

:code:`SessionException` will always contain two internal structures which can be used to iterate over the successful or failed tasks: :code:`successful_tasks` and :code:`exception_tasks`:

.. code-block:: python

    from restio.session import SessionException

    ...

    try:
        session.commit()  # raise_for_status=True, which calls Session.raise_for_status()
    except SessionException as exc:
        for successful_task in exc.successful_tasks:
            model = successful_task.model
            print(f"Model {model} persisted successfully")

        for failed_task, raised_exception in exc.exception_tasks:
            model = failed_task.model  # the model that failed to update
            print(f"Can't persist {model}: {raised_exception}")


Rollback
--------

:code:`Session.rollback` will only revert the local changes that have not yet been persisted. You can interpret this as a mechanism to revert all local changes (within the session) to their persistent state.

.. warning::
    Because server-side operations are done in multiple HTTP requests, it is not possible to guarantee atomicity between multiple requests. It is equally difficult to make sure that partial requests are reverted after they have been submitted. Therefore, a Session rollback **will not** undo changes already persisted on the server.

.. code-block:: python

    session = MySession()
    ...

    session.rollback()

Rollbacks are useful when the cache is populated with a lot of data. For example, if you have retrieved hundreds of models in order to analyze data and then further update a few models. If one update fails, you might still want to keep the data around to avoid loading everything again for the next operation.

.. _session_context_manager:

Context Manager
---------------

All session instances can be used as context managers. The code in :ref:`session_commit` could be re-written as follows:

.. code-block:: python

    async with MySession() as session:
        john = await session.get(Employee, 1)
        john.address = "Brazil"

        jay = Employee(name="Jay Pritchett", age=65, address="California")

Context managers simplify the manipulation of objects, the commit and the rollback workflows. The a context will automatically handle the following actions:

- **Adding models to the session**: If a model is instantiated within the context body for :code:`session`, then :code:`session.add()` is automatically called for that model.
- **Commit**: At the end of the context body, the session is automatically commited with :code:`session.commit(raise_for_error=True)`. If the call fails, the corresponding :code:`SessionException` is propagated back to the context.
- **Rollback on exception thrown**: Any exception thrown within the context body will first cause :code:`session.rollback()` to be triggered. The exception is propagated back to the context, and :code:`session.commit()` is never called.
- **Rollback on commit error**: If a commit fails, the context will automatically rollback the remaining non-persisted models with :code:`session.rollback()`.
