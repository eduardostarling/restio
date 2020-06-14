.. _example_usecase_without:

Implementation without restio
=============================

Step-by-Step
------------

A typical approach to interact with the API above is to represent the data as simple Python objects. It makes manipulating the data more intuitive:

.. code-block:: python

    class Employee:
        key: int
        name: str
        age: int
        address: str

        def __init__(self, key: int, name: str, age: int, address: str) -> None:
            self.key = key
            self.name = name
            self.age = age
            self.address = address


    class Company:
        key: str
        name: str
        employees: Set[Employee]

        def __init__(self, key: str, name: str, employees: Set[Employee]) -> None:
            self.key = key
            self.name = name
            self.employees = employees

        def hire_employee(self, employee: Employee):
            self.employees.add(employee)


The data mapping between the JSON response and the Python object could be done by consuming the API and extracting the needed values from the JSON data. Let's use :code:`aiohttp` to make the request and benefit from :code:`asyncio` event loops.

.. code-block:: python

    URL = "http://my-remote-rest-api"

    EMPLOYEES_URL = f"{URL}/employees"  # Employees Endpoint
    EMPLOYEE_URL = f"{EMPLOYEES_URL}/{{employee_key}}"  # Employee Endpoint

    COMPANIES_URL = f"{URL}/companies"  # Companies Endpoint
    COMPANY_URL = f"{COMPANIES_URL}/{{company_key}}"  # Company Endpoint

    COMPANY_EMPLOYEES_URL = f"{COMPANY_URL}/employees"  # Company Employees Endpoint
    COMPANY_EMPLOYEE_URL = f"{COMPANY_EMPLOYEES_URL}/{{employee_key}}"  # Company Employee Endpoint


    class Employee:
        key: int
        name: str
        age: int
        address: str

        def __init__(self, key: int, name: str, age: int, address: str) -> None:
            self.key = key
            self.name = name
            self.age = age
            self.address = address

        @staticmethod
        async def get(employee_key: int) -> Employee:
            url = EMPLOYEE_URL.format(employee_key=employee_key)

            result = await Employee.session.get(url)
            json_data = await result.json()
            return Employee.from_dict(json_data)

        @staticmethod
        def from_dict(dict_data: Dict[str, Any]) -> Employee:
            return Employee(key=dict_data["key"], name=dict_data["name"], age=dict_data["age"], address=dict_data["address"])

        def __hash__(self) -> int:
            return hash(self.key)


    class Company:
        key: str
        name: str
        employees: Set[Employee]

        def __init__(self, key: str, name: str, employees: Set[Employee]) -> None:
            self.key = key
            self.name = name
            self.employees = employees

        def hire_employee(self, employee: Employee):
            self.employees.add(employee)


    async def main():
        employee = await Employee.get(1000)
        print(employee)  # Employee(key=1000, name="Joseph Tribiani", age=25, address="1 Granville St, Vancouver, BC, VXX XXX, Canada")


    if __name__ == '__main__':
        asyncio.run(main())


The code above is good enough for retrieving an Employee's data. However, what if we now want to modify the address of Joseph? We could do that by simply implementing and extra method :code:`Employee.update` that updates the remote object by calling :code:`PUT`. Note that the Employee's :code:`key` needs to be defined by the API, so we don't provide any:

.. code-block:: python

    class Employee:
        ...

        async def update(self):
            url = EMPLOYEE_URL.format(employee_key=self.key)
            payload = json.dumps(self.to_dict())

            await self.session.put(url, data=payload.encode())

        def to_dict(self) -> Dict[str, Any]:
            return {
                "name": self.name,
                "age": self.age,
                "address": self.address
            }


Now, we can update the :code:`main` function to make the extra call:

.. code-block:: python

    async def main():
        joseph = await Employee.get(1000)
        joseph.address = "New address"

        # updates Joseph Tribiani's address
        await joseph.update()


If we talk about hiring new Employees to our Company, we should be able to do so by:
- implementing a method :code:`Employee.create` to request :code:`POST` on the Employee Endpoint (creates a new employee); and
- extending :code:`Company.hire_employee` to request :code:`PUT` on the Company Employee Endpoint (hires the employee).

We first implement :code:`Employee.create`. The :code:`POST` method returns the :code:`key` given to the new Employee in the Location header.

.. code-block:: python

    class Employee:
        ...

        async def create(self):
            url = EMPLOYEES_URL
            payload = json.dumps(self.to_dict())

            response = await self.session.post(url, data=payload.encode())

            # get the key created by the server
            location = response.headers["Location"]
            key = location.split("/")[-1]

            self.key = key


Once the Employee is created, we should make sure that he is hired to the correct Company. For that, we need to load the :code:`Company` object by implementing :code:`Company.get`. This implies also loading all employes that are already assigned to the :code:`Company` using :code:`Company.get_employees`:

.. code-block:: python

    class Company:
        ...

        @staticmethod
        async def get(company_key: str) -> Company:
            url_company = COMPANY_URL.format(company_key=company_key)

            response = await Company.session.get(url_company)
            json_data = await response.json()

            employees = await Company.get_employees(company_key)

            return Company.from_dict(json_data, employees=employees)

        @staticmethod
        async def get_employees(company_key: str) -> Set[Employee]:
            url_employees = COMPANY_EMPLOYEES_URL.format()

            response = await Company.session.get(url_employees)
            json_data = await response.json()
            return set(Employee.from_dict(e) for e in json_data)

        @staticmethod
        def from_dict(dict_data: Dict[str, Any], employees: Set[Employee]) -> Company:
            return Company(key=dict_data["key"], name=dict_data["name"], employees=employees)


And now we can extend :code:`Company.hire_employee()` in order to make the new Employee a part of the Company:

.. code-block:: python

    class Company:
        ...

        async def hire_employee(self, employee: Employee):
            url = COMPANY_EMPLOYEE_URL.format(
                company_key=self.key, employee_key=employee.key
            )

            await self.session.put(url)
            self.employees.add(employee)


Hiring a new employee :code:`Chandler Bing` to :code:`Amazing Company A` and modifying :code:`Joseph`'s address can now be done by writing :code:`main`:

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

.. literalinclude:: ../../../examples/company_employee_without_restio.py
