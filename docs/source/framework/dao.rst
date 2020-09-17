.. _dao:

Data Access Object
==================

The models described in :ref:`model` are unaware of how the remote REST API works and how to interact with it through HTTP requests.

**Data Access Objects** (from now on refered as **DAOs**) are used to trigger requests for a model in the REST API and map values in a transparent way. Requests handled by the DAO are typically CRUD.

Let's assume that a Client API library already exists to create :code:`Employee` models in the remote REST API:

.. code-block:: python

    from typing import Dict, Any

    import json
    import aiohttp


    class ClientAPI:
        session: aiohttp.ClientSession
        url = "http://my-remote-rest-api"

        def __init__(self):
            self.session = aiohttp.ClientSession(raise_for_status=True)

        async def create_employee(self, employee: Dict[str, Any]) -> int:
            employees_url = f"{self.url}/employees"
            payload = json.dumps(employee)

            response = await self.session.post(employees_url, data=payload.encode())

            # get the key created by the server
            location = response.headers["Location"]
            key = location.split("/")[-1]

            return int(key)


We can now use a **DAO** to persist the model :code:`Employee` using the :code:`ClientAPI`:

.. code-block:: python

    from typing import FrozenSet, Optional

    from restio.dao import BaseDAO
    from restio.fields import FrozenSetModelField, FrozenType, IntField, StrField
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


    class EmployeeDAO(BaseDAO[Employee]):
        api = ClientAPI()

        async def add(self, obj: Employee):
            employee_dict = self._map_to_dict(obj)
            key = await self.api.create_employee(employee_dict)

            # update the model with the key generated on the server
            obj.key = key

        @staticmethod
        def _map_to_dict(model: Employee) -> Dict[str, Any]:
            return dict(name=model.name, age=model.age, address=model.address)


At this point, it is already possible to interface with the remote server through the DAO:

.. code-block:: python

    # We now connect an EmployeeDAO object to an Employee model
    employee_dao = EmployeeDAO(Employee)

    # create a new employee locally
    employee_to_add = Employee(name="Carlos", age=52)

    # persist the employe on the remote server
    await employee_dao.add(employee_to_add)

    # new key has been assigned to the object
    employee_to_add.key  # 1234


**DAOs** on their own are not very useful. They need to be associated with a :code:`Transaction` instance in order to interact with **restio** properly (see :ref:`transaction` for more detail).

In order to be used by a :code:`Transaction`, **BaseDAO** contains 4 base methods that can potentially be overwritten: :code:`get`, :code:`add`, :code:`update` and :code:`remove`. None of these methods are purely abstract, which means that a **DAOs** can only have a few of them implemented. It is up to the developer to decide which methods to include.

+-----------+---------------+-------------------------+----------------------------------------------------------------+
| Method    | Caller        | Parameters              | When                                                           |
+===========+===============+=========================+================================================================+
| get       | Transaction   | Tuple with primary keys | Before, during or after a commit, when a model needs to        |
|           |               |                         | be retrieved from the server                                   |
+-----------+---------------+-------------------------+----------------------------------------------------------------+
| add       | Transaction   | Model object            | During a commit, when a model is to be added to the server     |
+-----------+---------------+-------------------------+----------------------------------------------------------------+
| update    | Transaction   | Model object            | During a commit, when a model is to be updated in the server   |
+-----------+---------------+-------------------------+----------------------------------------------------------------+
| remove    | Transaction   | Model object            | During a commit, when a model is to be removed from the server |
+-----------+---------------+-------------------------+----------------------------------------------------------------+

A complete implementation of the :code:`EmployeeDAO` and :code:`ClientAPI` for all CRUD operations can be seen below:

.. code-block:: python

    from typing import Dict, Any, FrozenSet, Optional

    import json
    import aiohttp

    from restio.dao import BaseDAO
    from restio.fields import FrozenSetModelField, FrozenType, IntField, StrField
    from restio.model import BaseModel


    class ClientAPI:
        session: aiohttp.ClientSession
        url = "http://my-remote-rest-api"

        def __init__(self):
            self.session = aiohttp.ClientSession(raise_for_status=True)

        async def get_employee(self, key: int) -> Dict[str, Any]:
            employee_url = f"{self.url}/employees/{key}"
            result = await self.session.get(employee_url)
            return await result.json()

        async def create_employee(self, employee: Dict[str, Any]) -> int:
            employees_url = f"{self.url}/employees"
            payload = json.dumps(employee)

            response = await self.session.post(employees_url, data=payload.encode())

            # get the key created by the server
            location = response.headers["Location"]
            key = location.split("/")[-1]

            return int(key)

        async def update_employee(self, key: int, employee: Dict[str, Any]):
            employee_url = f"{self.url}/employees/{key}"
            payload = json.dumps(employee)
            await self.session.put(employee_url, data=payload.encode())

        async def remove_employee(self, key: int):
            employee_url = f"{self.url}/employees/{key}"
            await self.session.delete(employee_url)


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


    class EmployeeDAO(BaseDAO[Employee]):
        api = ClientAPI()

        # Employee only contains one pk `key`, so it must be an argument
        async def get(self, *, key: str) -> Employee:
            employee_data = await self.api.get_employee(key)
            return self._map_from_dict(employee_data)

        async def add(self, obj: Employee):
            employee_dict = self._map_to_dict(obj)
            key = await self.api.create_employee(employee_dict)

            # update the model with the key generated on the server
            obj.key = key

        async def update(self, obj: Employee):
            employee_dict = self._map_to_dict(obj)
            await self.api.update_employee(obj.key, employee_dict)

        async def remove(self, obj: Employee):
            await self.api.remove_employee(obj.key)

        @staticmethod
        def _map_from_dict(data: Dict[str, Any]) -> Employee:
            employee = Employee(name=str(data["name"]), age=int(data["age"]), address=str(data["address"]))
            employee.key = int(data["key"])
            return employee

        @staticmethod
        def _map_to_dict(model: Employee) -> Dict[str, Any]:
            return dict(name=model.name, age=model.age, address=model.address)
