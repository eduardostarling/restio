import asyncio
from typing import List, Optional, Tuple

import requests

from restio.dao import BaseDAO
from restio.model import BaseModel, PrimaryKey, ValueKey, mdataclass, pk
from restio.query import query
from restio.transaction import Transaction


class ClientAPI:
    """
    Simple client API to consume dummy.restapiexample.com
    """
    URL = "http://dummy.restapiexample.com/api/v1"
    headers = {"Accept": "text/json", "User-Agent": "XY"}

    def get_employee(self, employee_id: int):
        url = self.get_url(f"employee/{employee_id}")
        response = requests.get(url, headers=self.headers)
        return self._process_response(response)

    def get_employees(self):
        response = requests.get(self.get_url(f"employees"), headers=self.headers)
        return self._process_response(response)

    def _process_response(self, response):
        if response.ok:
            return response.json()

        raise RuntimeError(response)

    def get_url(self, route: str):
        return f"{self.URL}/{route}"


@mdataclass
class Employee(BaseModel):
    id: PrimaryKey[int] = pk(int)
    name: str = ""
    age: int = 0
    salary: float = 0.0


class EmployeeDAO(BaseDAO):
    client = ClientAPI()

    async def get(self, obj: Tuple[ValueKey[int]]) -> Employee:
        json = self.client.get_employee(obj[0])
        return self._get_model(json)

    def _get_model(self, json):
        return Employee(
            id=PrimaryKey(int, int(json['id'])), name=str(json['employee_name']),
            age=int(json['employee_age']), salary=float(json['employee_salary']))


@query
async def get_employees(self, dao: EmployeeDAO) -> List[Employee]:
    employees = dao.client.get_employees()
    return [dao._get_model(x) for x in employees[:10]]


async def main():
    # initializes the framework and registers the models
    # and DAO's to the transaction scope
    t: Transaction = Transaction()
    dao = EmployeeDAO(Employee)
    t.register_dao(dao)

    # loads a list of employees from the remote server
    # using a query function
    q = get_employees(dao)
    employees: List[Employee] = await t.query(q)

    print("Size: ", len(employees))
    print("First employee: ", employees[0])

    # gets the primary keys
    employee_id = employees[0].id.get()

    # resets the transaction by clearing the cache
    t.reset()

    # retrieves the selected employee from the remote
    # the loop exists to validate the cache only - the
    # first call will make the request, while the rest
    # will be ignored
    employee: Optional[Employee]

    for _ in range(0, 10):
        employee = await t.get(Employee, employee_id)
    print("Manually loaded employee: ", employee)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
