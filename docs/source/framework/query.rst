.. _query:

Queries
=======

Queries are useful when data needs to be retrieved from the remote REST API in custom ways.

Considering the Employee example model from :ref:`model`:

.. code-block:: python

    from restio.fields import IntField, StrField, FrozenType
    from restio.model import BaseModel

    class Employee(BaseModel):
        key: IntField = IntField(pk=True, allow_none=True, frozen=FrozenType.ALWAYS)
        name: StrField = StrField()
        age: IntField = IntField(default=18)
        address: StrField = StrField(default="Company Address")

        ...

The :code:`EmployeeDAO` implemented at :ref:`dao` knows how to retrieve such model through the :code:`get` method:

.. code-block:: python

    ...

    class EmployeeDAO(BaseDAO[Employee]):
        api = ClientAPI()

        async def get(self, *, key: int) -> Employee:
            employee_dict = await api.get_employee(key)
            return self._from_dict(employee_dict)
        ...

What if we wish to retrieve a list of employees in one go, by their keys?

Without a custom query, one could easily call :code:`Session.get` several times, for each employee key:

.. code-block:: python

    session = Session()
    session.register_dao(EmployeeDAO(Employee))
    ...

    keys = (1000, 1002, 1004, 1008)
    employees = [await session.get(Employee, key=key) for key in keys]

The issue with the above code is that the calls to :code:`Session.get` can be expensive, because they require sending an individual request to the remote server for each key in the tuple.

A much better approach could be to write a custom query that uses a readily-available endpoint that supports filtering:

.. code-block:: python

    from restio.query import query

    ...

    class EmployeeDAO(BaseDAO[Employee]):
        api = ClientAPI()

        ...

        @query
        @classmethod
        async def get_with_filter(cls, keys: Tuple[int, ...]) -> Tuple[Employee, ...]:
            comma_keys = ",".join(keys)  # creates a comma-separated list of keys for filtering
            employees_list = cls.api.get_with_filter(comma_keys)  # assuming this endpoint exists

            return [self._from_dict(e) for e in employees_dict]

It is now easy to retrieve the list of Employees by their keys:

.. code-block:: python

    session = Session()
    session.register_dao(EmployeeDAO(Employee))
    ...

    keys = (1000, 1002, 1004, 1008)
    employees = await session.query(EmployeeDAO.get_with_filter(keys))


Writing a query
---------------

All **restio** query instances are `coroutine functions <https://docs.python.org/3/glossary.html#term-coroutine-function>`_ wrapped as an instance of :code:`restio.query.BaseQuery`. The decorator :code:`query` (imported from :code:`restio.query`) makes it easy to transform any function or method into a query that a :code:`Session` can understand.

.. code-block:: python

    from restio.query import query

    @query
    async def my_query(arg1, arg2) -> List[Model]:
        return [Model(arg1=arg1, arg2=arg2)]

    q = my_query(1, 2)  # BaseQuery instance
    models = await session.query(q)  # (Model(arg1=1, arg2=2),)

    print(models[0])    # Model(arg1=1, arg2=2)


The query is executed only when injecting it into a :code:`Session.query()` instance call. This is to make sure that the returned models are properly registered in the cache of the :code:`Session`.

Queries should **always** return iterable types. The value is always stored and returned by the :code:`Session` as a :code:`tuple` (to guarantee that the order is preserved).


Query uniqueness
----------------

Two query instances are considered equal when:

- the coroutine function from which they derive is the same
- the provided arguments are equal


.. code-block:: python

    q1 = my_query(1, 2)
    q2 = my_query(1, 2)
    q3 = my_query(2, 2)

    q1 == q2  # True
    q1 == q3  # False

Query uniqueness is used for caching purposes.

Calling :code:`Session.query()` for the same session instance, with the same query twice, will result in only one effective call to the query (the results from the second call are returned from the cache). One can force re-running the query again by calling :code:`Session.query()` with :code:`force=True`.

.. note::
    Using :code:`force=True` will not replace existing models that are already in cache. If the query returns a model with similar type and primary key, but different content, then the model stored in cache will overtake the model returned by the query. Please see :ref:`caching` for details.


Injecting the Session instance
------------------------------

:code:`BaseQuery` instances are independent from a :code:`Session` instance. However, in some cases it is useful to be able to access the current session from within the coroutine function itself.

A special argument :code:`session` can be used for that purpose:

.. code-block:: python

    @query
    async def query_with_session(arg1, arg2, session) -> List[Model]:
        print(arg1, arg2, session)

    session = Session()

    await session.query(query_with_session(1, 2))   # 1, 2, <restio.session.Session object at ...>

**restio** automatically detects if the parameter :code:`session` is expected by the coroutine function, and injects it at runtime in such case.
