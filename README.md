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

You can install the latest pre-release version of **restio** as a dependency to your project with pip:

```bash
pip install --pre restio
```

## Practical Example

A typical REST Client API implemented with **restio** looks like the following:

```python
from __future__ import annotations

from typing import Dict, Any, Optional

import aiohttp
import json

from restio.dao import BaseDAO
from restio.fields import ModelField, IntField, StrField
from restio.model import BaseModel
from restio.session import Session


# Model definition - this is where the relational data schema is defined

class Employee(BaseModel):
    key: IntField = IntField(pk=True, allow_none=True, frozen=FrozenType.ALWAYS)
    name: StrField = StrField()
    age: IntField = IntField()
    address: StrField = StrField(default="Company Address")
    boss: ModelField[Optional[Employee]] = ModelField("Employee", allow_none=True)


# Data access object definition - teaches restio how to deal with
# CRUD operations for a relational model

class EmployeeDAO(BaseDAO[Employee]):
    client_session: aiohttp.ClientSession = aiohttp.ClientSession(raise_for_status=True)
    url = "http://remote-rest-api-url"

    async def get(self, *, key: int) -> Employee:
        employee_url = f"{self.url}/employees/{key}"
        result = await self.client_session.get(employee_url)
        employee_data = await result.json()

        # asks the current session to retrieve the boss from cache or
        # to reach to the remote server
        boss = await self.session.get(Employee, key=employee_data["boss"])

        return self._map_from_dict(employee_data, boss)

    async def add(self, obj: Employee):
        employees_url = f"{self.url}/employees"
        payload = json.dumps(self._map_to_dict(obj))

        response = await self.client_session.post(employees_url, data=payload.encode())

        location = response.headers["Location"]
        key = location.split("/")[-1]

        # update the model with the key generated on the server
        obj.key = key

    @staticmethod
    def _map_from_dict(data: Dict[str, Any], boss: Employee) -> Employee:
        return Employee(
            key=int(data["key"]),
            name=str(data["name"]),
            age=int(data["age"]),
            address=str(data["address"]),
            boss=boss
        )

    @staticmethod
    def _map_to_dict(model: Employee) -> Dict[str, Any]:
        return dict(
            name=model.name,
            age=model.age,
            address=model.address,
            boss=model.boss.key
        )
```

Once `Models` and `Data Access Objects` (DAOs) are provided, you can use `Sessions` to operate the `Models`:

```python
# instantiate the Session and register the DAOs EmployeeDAO
# to deal with Employee models
session = Session()
session.register_dao(EmployeeDAO(Employee))

# initialize session context
async with session:
    # retrieve John Doe's Employee model, that has a known primary key 1
    john = await session.get(Employee, key=1)  # Employee(key=1, name="John Doe", age=30, address="The Netherlands")

    # create new Employees in local memory
    jay = Employee(name="Jay Pritchett", age=65, address="California")
    manny = Employee(name="Manuel Delgado", age=22, address="Florida", boss=jay)

# at the end of the context, `session.commit()` is called automatically
# and changes are propagated to the server
```

## Overview

When consuming remote REST APIs, the data workflow used by applications normally differs from the one done with ORMs accessing relational databases.

With databases, it is common to use transactions to guarantee atomicity when persisting data on these databases. Let's take a Django-based application example of a transaction (example is minimal, fictitious and adapted from https://docs.djangoproject.com/en/3.1/topics/db/transactions/):

```python
from django.db import DatabaseError, transaction
from mylocalproject.models import Person

def people():
    try:
        with transaction.atomic():
            person1 = Person(name="John", age=1)
            person2 = Person(name="Jay", age=-1)  # mistake!

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
from restapiclient import ClientAPI, Person

client = ClientAPI()

def people():
    person1: Person = client.create_person(name="John", age=1)   # ok
    person2: Person = client.create_person(name="Jay", age=-1)  # error, exit

    person1.friends.add(person2)
    client.update_person(person1)
```

In this case, not only the calls to the server are done synchronously, but the data validation of `person2` would be done too late (either by the client API or the server). Since `person1` was already added, now we have garbage left on the remote server.

**restio** is designed to optimize this and other cases when interacting with REST APIs. It does it in a way that it is more intuitive for developers that are already familiar with ORMs and want to use a similar approach, with similar benefits.

Please visit the [official documentation](https://restio.readthedocs.io/en/latest/) for more information.
