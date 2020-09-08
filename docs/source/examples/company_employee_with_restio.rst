.. _example_usecase_with:

Implementation with restio
==========================

Step-by-Step
------------

Data models
^^^^^^^^^^^

We start by understanding the two provided data models: :code:`Employee` and :code:`Company`.

- :code:`Employee` has one integer **key** identifier that is set by the server and cannot be modified (the primary key). All other fields :code:`name`, :code:`age` and :code:`address` can be modified at any time.
- :code:`Company` has one string **key** identifier that is set by the server and cannot be modified (the primary key), and a :code:`name` that also cannot be modified.
- :code:`Company` has a many-to-many relationship with :code:`Employee` (one company has many employees, one employee can work part-time for several companies).
- :code:`Employee` can be fully controlled through the API (get, add, update, remove) while a :code:`Company` can only be retrieved (get) or updated (update).

Therefore, we can write the data models as follows:

.. code-block:: python

    from restio.model import BaseModel
    from restio.fields import IntField, StrField, FrozenSetModelField, FrozenType


    class Employee(BaseModel):
        key: IntField = IntField(pk=True, allow_none=True, frozen=FrozenType.ALWAYS)
        name: StrField = StrField()
        age: IntField = IntField()
        address: StrField = StrField()

        def __init__(self, *, name: str, age: int, address: str):
            self.name = name
            self.age = age
            self.address = address


    class Company(BaseModel):
        key: StrField = StrField(pk=True, frozen=FrozenType.ALWAYS)
        name: StrField = StrField(frozen=FrozenType.ALWAYS)
        employees: FrozenSetModelField = FrozenSetModelField(
            Employee, frozen=FrozenType.CREATE
        )

        def __init__(self, *, key: str, name: str):
            self.key = key
            self.name = name

        def hire_employee(self, employee: Employee):
            self.employees = self.employees.union({employee})


Client API
^^^^^^^^^^

We write a separate module :code:`ClientAPI` that is responsible for making all the requests to the remote API. This module does not need to be aware of **restio** and can be limited to manipulate only raw data (dictionaries or JSON strings).

.. note::
    In a lot of existing use cases, this will be already implemented.

.. code-block:: python

    URL = "http://my-remote-rest-api"

    EMPLOYEES_URL = f"{URL}/employees"  # Employees Endpoint
    EMPLOYEE_URL = f"{EMPLOYEES_URL}/{{employee_key}}"  # Employee Endpoint

    COMPANIES_URL = f"{URL}/companies"  # Companies Endpoint
    COMPANY_URL = f"{COMPANIES_URL}/{{company_key}}"  # Company Endpoint

    COMPANY_EMPLOYEES_URL = f"{COMPANY_URL}/employees"  # Company Employees Endpoint
    COMPANY_EMPLOYEE_URL = f"{COMPANY_EMPLOYEES_URL}/{{employee_key}}"  # Company Employee Endpoint

    # Type aliases
    EmployeeDict = Dict[str, Any]
    CompanyDict = Dict[str, Any]


    class ClientAPI:
        session: aiohttp.ClientSession

        def __init__(self):
            self.session = aiohttp.ClientSession(raise_for_status=True)

        # Employees Endpoints

        async def get_employee(self, key: int) -> EmployeeDict:
            url = EMPLOYEE_URL.format(employee_key=key)
            result = await self.session.get(url)
            return await result.json()

        async def create_employee(self, employee: EmployeeDict) -> int:
            payload = json.dumps(employee)
            response = await self.session.post(EMPLOYEES_URL, data=payload.encode())

            # get the key created by the server
            location = response.headers["Location"]
            key = location.split("/")[-1]

            return int(key)

        async def update_employee(self, key: int, employee: EmployeeDict):
            url = EMPLOYEE_URL.format(employee_key=key)
            payload = json.dumps(employee)
            await self.session.put(url, data=payload.encode())

        async def remove_employee(self, key: int):
            url = EMPLOYEE_URL.format(employee_key=key)
            await self.session.delete(url)

        async def get_all_employees(self) -> List[EmployeeDict]:
            result = await self.session.get(EMPLOYEES_URL)
            return await result.json()

        # Company Endpoints

        async def get_company(self, key: str) -> CompanyDict:
            url = COMPANY_URL.format(company_key=key)
            result = await self.session.get(url)
            return await result.json()

        async def get_all_companies(self) -> List[CompanyDict]:
            result = await self.session.get(COMPANIES_URL)
            return await result.json()

        # Company Employee Endpoints

        async def get_company_employees(self, company_key: str) -> List[EmployeeDict]:
            url = COMPANY_EMPLOYEES_URL.format(company_key=company_key)
            result = await self.session.get(url)
            return await result.json()

        async def add_employee_to_company(self, company_key: str, employee_key: int):
            url = COMPANY_EMPLOYEE_URL.format(
                company_key=company_key, employee_key=employee_key
            )
            await self.session.put(url)

        async def remove_employee_from_company(self, company_key: str, employee_key: int):
            url = COMPANY_EMPLOYEE_URL.format(
                company_key=company_key, employee_key=employee_key
            )
            await self.session.delete(url)


Data Access Objects
^^^^^^^^^^^^^^^^^^^

In order to teach **restio** how to use the :code:`ClientAPI` and map the API data into the models we already created, we should implement two DAOs: one for :code:`Employee` and one for :code:`Company`.

The strategy is straight-forward:

- For every DAO, we implement the methods that are allowed by the API.

    - :code:`EmployeeDAO`: :code:`get`, :code:`add`, :code:`update` and :code:`remove`.
    - :code:`CompanyDAO`: :code:`get` and :code:`update`.

- We create a single shared object :code:`api` to be accessed by any DAO instance.
- In each of the above we call the corresponding method in the :code:`ClientAPI`.
- If a model depends on another model (e.g. :code:`Company` depends on :code:`Employee`), we ask the :code:`Transaction` to load the dependencies (not the :code:`ClientAPI` directly!) using a custom :code:`query` to do the caching of results.
- We create helper methods to map the dictonary data to models, and vice-versa.


First, the :code:`EmployeeDAO`:

.. code-block:: python

    from restio.dao import BaseDAO
    from restio.query import query

    # alternatively, you could also extend BaseDAO and include this
    # as a static member
    api = ClientAPI()


    class EmployeeDAO(BaseDAO[Employee]):
        # the argument `key` matches the primary key name of Employee
        async def get(self, *, key: int) -> Employee:
            employee_dict = await api.get_employee(key)

            # once returned, the instance is immediately cached
            # and given to the caller
            return self._from_dict(employee_dict)

        async def add(self, obj: Employee):
            # creates the employee on the remote server
            key = await api.create_employee(self._to_dict(obj))

            # we should give the key back to the original instance
            obj.key = key

        async def update(self, obj: Employee):
            # regular update on the remote
            await api.update_employee(obj.key, self._to_dict(obj))

        async def remove(self, obj: Employee):
            # regular delete on the remote
            await api.remove_employee(obj.key)

        @staticmethod
        def _to_dict(employee: Employee) -> EmployeeDict:
            return dict(name=employee.name, age=employee.age, address=employee.address)

        @staticmethod
        def _from_dict(employee_dict: EmployeeDict) -> Employee:
            employee = Employee(
                name=employee_dict["name"],
                age=employee_dict["age"],
                address=employee_dict["address"],
            )
            employee.key = employee_dict["key"]

            return employee

And then the :code:`CompanyDAO`:

.. code-block:: python

    class CompanyDAO(BaseDAO[Company]):
        async def get(self, *, key: str) -> Company:
            company_dict = await api.get_company(key)

            # instantiates the company object
            company = self._from_dict(company_dict)

            # now we load all the employees that belong to the company
            company_employees_query = self.get_company_employees(company_key=key)
            # this will not only retrieve all the company employees, but will also
            # register all the loaded employees to the cache - the `force` argument
            # is used to tell the transaction to execute the query again, without
            # replacing the models that are already in the cache
            company_employees = await self.transaction.query(
                company_employees_query, force=True
            )

            # query results are tuples, so we need to convert
            company.employees = frozenset(company_employees)

            return company

        @query
        @classmethod
        async def get_company_employees(
            cls, company_key: str, *, transaction
        ) -> FrozenSet[Employee]:
            employees_list = await api.get_company_employees(company_key)
            return frozenset(EmployeeDAO._from_dict(e) for e in employees_list)

        async def update(self, obj: Company):
            # we will populate these with data only if there are
            # employees to be added or removed from the company
            added_employees: FrozenSet[Employee] = frozenset()
            removed_employees: FrozenSet[Employee] = frozenset()

            # checks if the "employees" field has been modified -
            # in this case, this check is superfluous because this is
            # the only field that can change, but for other models
            # this could be different
            if obj.is_field_modified("employees"):
                added_employees = obj.employees - obj._persistent_values["employees"]
                removed_employees = obj._persistent_values["employees"] - obj.employees

            # triggers all requests concurrently, for maximum performance
            await asyncio.gather(
                self._add_employees(obj, added_employees),
                self._remove_employees(obj, removed_employees),
            )

        async def _add_employees(self, company: Company, employees: FrozenSet[Employee]):
            await self._gather_tasks(company, employees, api.add_employee_to_company)

        async def _remove_employees(self, company: Company, employees: FrozenSet[Employee]):
            await self._gather_tasks(company, employees, api.remove_employee_from_company)

        @staticmethod
        async def _gather_tasks(
            company: Company,
            employees: FrozenSet[Employee],
            method: Callable[[str, int], Any],
        ):
            tasks = []
            for employee in employees:
                task = asyncio.create_task(method(company.key, employee.key))
                tasks.append(task)

        @staticmethod
        def _from_dict(company_dict: CompanyDict) -> Company:
            return Company(key=company_dict["key"], name=company_dict["name"])


Hiring a new employee :code:`Chandler Bing` to :code:`Amazing Company A` can now be done by implementing :code:`main`. Note that all the requests to persist data are done in :code:`transaction.commit()`:


.. code-block:: python

    async def main():
        transaction = Transaction()
        transaction.register_dao(EmployeeDAO(Employee))
        transaction.register_dao(CompanyDAO(Company))

        # loads Joseph Tribiani
        joseph = await transaction.get(Employee, key=1000)
        # loads the Amazing Company A
        company_a = await transaction.get(Company, key="COMPANY_A")

        # updates Joseph Tribiani's address
        joseph.address = "New address"

        # hires Chandler Bing, that lives together with Joseph
        chandler = Employee(name="Chandler Bing", age=26, address=joseph.address)
        company_a.hire_employee(chandler)

        # this is where all the requests are effectively made
        await transaction.commit()


Full source code
----------------

.. literalinclude:: ../../../examples/company_employee_with_restio.py
