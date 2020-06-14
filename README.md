# restio

**restio** is a Python ORM-like framework that manages relational data coming from remote REST APIs, in a similar way that is done for databases.

Some of the advantages of using **restio** in comparison with raw REST Client APIs:

- Clear decoupling between models and data access logic.
- Client-side caching of models and queries.
- Improved performance for nearly all operations with native use of `asyncio`.
- Type-checking and data validation.
- Model state management.
- Rich relational models and dependency management.
- Fully integrated with type-hinting.

[Official documentation](https://restio.readthedocs.io/en/latest/)

## Installation

### Requirements

- Python 3.7+

### Pip

You can install **restio** as a dependency to your project with pip:

```bash
pip install restio
```

## Practical Example

A typical REST Client API implemented with **restio** looks like the following:

```python
from typing import Dict, Any

import json
import aiohttp

from restio.dao import BaseDAO
from restio.transaction import Transaction


# the raw client API, typically implemented by the client application
# or provided as a third-party library by the API owner

class ClientAPI:
    session: aiohttp.ClientSession
    url = "http://remote-rest-api-url"

    def __init__(self):
        self.session = aiohttp.ClientSession(raise_for_status=True)

    async def get_employee(self, key: int) -> Dict[str, Any]:
        employee_url = f"{self.url}/employees/{key}"
        result = await self.session.get(employee_url)
        return await result.json()

    async def create_employee(self, employee: Dict[str, Any]) -> int:
        employees_url = f"{self.url}/employees"
        payload = json.dumps(employee)

        await self.session.post(employees_url, data=payload.encode())

        new_employee_data = await self.get_employee_by_name(employee["name"])
        return int(new_employee_data["key"])

    async def update_employee(self, key: int, employee: Dict[str, Any]):
        employee_url = f"{self.url}/employees/{key}"
        payload = json.dumps(employee)
        await self.session.put(employee_url, data=payload.encode())

    async def remove_employee(self, key: int):
        employee_url = f"{self.url}/employees/{key}"
        await self.session.delete(employee_url)

    async def get_employee_by_name(self, name: str) -> Dict[str, Any]:
        employees_url = f"{self.url}/employees"
        result = await self.session.get(employees_url)
        employees = await result.json()

        for employee in employees:
            if employee["name"] == name:
                return employee

        raise RuntimeError(f"Employee with name {name} not found.")


# Model definition - this is where the relational data schema
# is defined

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


# Data access object definition - teaches restio how to deal with
# CRUD operations for a relational model

class EmployeeDAO(BaseDAO[Employee]):
    api = ClientAPI()

    async def get(self, *, key: str) -> Employee:
        key, = pks  # Employee only contains one pk

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
```

Once `Models` and `Data Access Objects` (DAOs) are provided, you can use `Transactions` to operate the `Models`:

```python

async def alter_employees():
    # instantiate the Transaction and register the DAOs EmployeeDAO
    # to deal with Employee models
    t = Transaction()
    t.register_dao(EmployeeDAO(Employee))

    # retrieve John Doe's Employee model, that has a known primary key 1
    john = await t.get(Employee, 1)   # Employee(key=1, name="John Doe", age=30, address="The Netherlands")
    john.address = "Brazil"

    # create a new Employee model Jay Pritchett in local memory
    jay = Employee(name="Jay Pritchett", age=65, address="California")
    # tell the transaction to add the new employee to its context
    t.add(jay)

    # persist all changes on the remote server
    await t.commit()

await alter_employees()

```

## Introduction

When consuming remote REST APIs, the data workflow used by applications normally differs from the one done with ORMs accessing relational databases.

With databases, it is common to use transactions to guarantee atomicity when persisting data on these databases. Let's take a Django-based application example of a transaction (example is minimal, fictitious and adapted from https://docs.djangoproject.com/en/3.1/topics/db/transactions/):

```python
from django.db import DatabaseError, transaction
from mylocalproject.models import Person

def people():
    try:
        with transaction.atomic():
            person1 = Person(name="John", age=1)
            person2 = Person(name="Jay", age=-1)

            person1.friends.add(person2)

            person1.save()
            person2.save()
    except DatabaseError as err:
        # rollback is already done here, no garbage left on the database
        print(err)  # Person can't have age smaller than 0
```

For remote REST APIs, guaranteeing atomicity becomes a difficult job, as each call to the remote API should be atomic.
If the same code above was to be called to a REST API client, you would typically see the following:

```python
import restapiclient, Person

client = restapiclient.ClientAPI()

def people():
    person1: Person = client.create_person(name="John", age=1)   # ok
    person2: Person = client.create_person(name="Jay", age=-1)  # error, exit

    person1.friends.add(person2)
    client.update_person(person1)
```

In this case, not only the calls to the server are done synchronously, but the data validation of `person2` would be done too late (either by the client API or the server). Since `person1` was already added, now we have garbage left on the remote server.

**restio** is designed to optimize this and other cases when interacting with REST APIs. It does it in a way that it is more intuitive for developers that are already familiar with ORMs and want to use a similar approach, with similar benefits.

Please visit the [official documentation](https://restio.readthedocs.io/en/latest/) for more information.
