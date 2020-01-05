
# Framework

The **restio** framework is composed by a few building blocks:

- Model
- Data Access Object
- Transaction

On high level, Transactions are supposed to coordinate contexts of operations on a remote REST API. Transactions benefit from the relationship between Data Access Objects and Models to decide how models are persisted on the remote server.

Below, a you will find more detailed explanations of each module and how we can connect them together.

## Model

A model is a representation of a real world object in software context. All models that can be used by the framework should inherit from its basic construction, **_BaseModel_**. **BaseModel** will guarante that the models stored locally contain all necessary metadata for an efficient operation with the remote server through a Transaction.

For example, a model **_Person_** could be written using as following to represent a Person stored in a remote REST API:

```python
from restio import BaseModel, mdataclass, PrimaryKey

@mdataclass
class Person(BaseModel):
    id: PrimaryKey[int] = PrimaryKey(int)
    name: str = ""
    age: int = 0
    address: str = ""

    def change_address(self, new_address: str):
        if not new_address:
            raise ValueError("Invalid address.")
        self.address = new_address

```

Models within the framework could be decorated as [dataclasses](https://docs.python.org/3/library/dataclasses.html), and this is the recommended approach. On the example above, we use our own wrapper decorator **mdataclass** that will transform **_Person_** into a dataclass on the background. If not using dataclasses, please make sure that the constructor of **BaseModel** is called. All examples in this documentation will use dataclasses to define models.

Naturally, a model on the remote server could contain relationships with other models types. It is possible to replicate that behavior on the client side. For example, if we need to represent a **_Company_** model as a remote object, we could simple extend the code above with the following:

```python
from dataclass import field
from typing import Set

# code snippet above

@mdataclass
class Company(BaseModel):
    name: PrimaryKey[str] = PrimaryKey(str)
    employees: Set[Person] = field(default_factory=frozenset)

    def hire_employee(self, employee: Person):
        # we need to re-set the attribute to signalize to the framework
        # that the model has changed
        self.employees = frozenset(self.employees.union({employee}))

```

It is now easy to manipulate objects in the business logic layer (BLL) of the application:

```python
employee_a = Person(id=1, name="Alice", age=27)  # retrieved from the remote
company = Company(name="RestIOCompany", address="old_address", employees=frozenset({employee_a}))
...
new_employee = Person(id=2, name="Bob", age=19)  # retrieved from the remote
company.hire_employee(new_employee)
```

## Data Access Object

The abstractions seen on section above should be translated into objects from the remote REST API. The models themselves don't know how CRUD operations are done through HTTP requests, and therefore need another layer to indicate how to handle each object type. This is when the **Data Access Object**s (from now on refered as **DAO**s) play an important role.

Let's assume that a Client API library exists with a method to create a particular *Person* object in a remote REST API:

```python
from typing import Dict, Any

import json
import aiohttp

...

class ClientAPI:
    url = "http://my-remote-rest-api"

    async def create_person(person: Dict[str, Any]) -> bool:
        payload = json.dumps(person)
        person_url = f"{self.url}/person"

        async with aiohttp.ClientSession() as session:
            async with session.put(person_url, data=payload.encode()) as resp:
                if resp.status != 200:
                    raise RuntimeError("Error when performing request.")
    ...
```

We can now use a *DAO* to create a relationship between the model *Person* and the module *ClientAPI*:

```python
from restio import BaseDAO

...

class PersonDAO(BaseDAO):
    api = ClientAPI()

    async def add(obj: Person):
        person_dict = self._map_to_dict(obj)
        await self.api.create_person(person_dict)

    async def _map_to_dict(model: Person) -> Dict[str, Any]:
        return dict(id=model.id, name=model.name, age=model.age, address=model.address)

# We now connect a PersonDAO object to a Person model
person_dao = PersonDAO(Person)
```

At this point, it is already possible to interface with the remote server through the DAO:

```python
# create a new employee locally
employee_to_add = Person(id=3, name="Carlos", age=52)

# persist the employe on the remote server
await person_dao.add(employee_to_add)
```

The operation above already allows a better decoupling between business and data access, but still doesn't solve the problem of performance. This is when the Transaction module comes into play.

## Transaction

A transaction instance is supposed to resemble a database transaction, but it aims to be used within the context of REST APIs. With this module, we try to solve common problems faced when using a REST API, such as caching, persistency, state management and performance. You can instantiate a transaction by simply implementing:

```python
from restio import Transaction

t = Transaction()
```

Differently from a normal relational database, a generic REST API is stateless and does not implement internal transactions. Therefore, *it is never guaranteed that the transaction is atomic when interacting with the remote server*. However, replicating the remote models as local abstractions within the Transaction module allows the framework to anticipate common issues, such as model relationship inconsistencies. By using the Transaction abstraction in the BLL, it is possible to write business rules that are decoupled from the data access.

Going back to the example shown in the section above, let's now use the Transaction to add a new employee to the remote API:

```python

....

# informs the transaction about the relationship between PersonDAO and Person
t.register_dao(person_dao)

# create a new employee locally
employee_to_add = Person(id=3, name="Carlos", age=52)

# tells the transaction to add the new employee to its context
t.add(employee_to_add)
```

It is important to understand that at this point, no operation has been done to the remote server *yet*. It is necessary to tell the Transaction to **commit** its changes explicitly:

```python
...

await t.commit()
```

The *commit* method will inspect all models stored on the transaction's internal cache and verify which models should be modified. Its is not up to the BLL anymore to figure out in which order the operations need to be persisted on the remote server, and which models are unchanged. The transaction will take care of drawing the graph of dependencies between models and trigger all requests to the remote REST API accordingly.

If anything goes wrong when processing a model, then it is possible to revisit all tasks performed by the commit:

```python
from restio import DAOTask

...

tasks = await t.commit()

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
```

# More information

The page [Strategies](STRATEGIES.md) contains important information about the internals of *restio*. Please read this page if you consider using this framework in production.

For other examples, please refer to the [examples](examples/) folder.