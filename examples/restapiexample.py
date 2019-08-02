import asyncio
from typing import List, Optional, Tuple

import requests

from restio.dao import BaseDAO
from restio.model import BaseModel, PrimaryKey, mdataclass, pk
from restio.query import query
from restio.transaction import Transaction


class ClientAPI:
    """
    Simple client API to consume dummy.restapiexample.com
    """
    URL = "http://dummy.restapiexample.com/api/v1"
    headers = {"Accept": "text/json", "User-Agent": "XY"}

    def get_employee(self, key: Tuple[PrimaryKey[int]]):
        employee_id = key[0].get()
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

    async def get(self, obj: Tuple[PrimaryKey[int]]) -> Employee:
        json = self.client.get_employee(obj)
        return self._get_model(json)

    def _get_model(self, json):
        return Employee(
            id=PrimaryKey(int, int(json['id'])), name=str(json['employee_name']),
            age=int(json['employee_age']), salary=float(json['employee_salary']))


@query
async def get_employees(self, dao: EmployeeDAO) -> List[Employee]:
    employees = dao.client.get_employees()
    return [dao._get_model(x) for x in employees[:3000]]


async def main():
    t: Transaction = Transaction()
    dao = EmployeeDAO(Employee)
    t.register_dao(dao)

    for _ in range(0, 20):
        employee: Optional[Employee] = await t.get(Employee, PrimaryKey(int, 9830))
        print(employee)

    q = get_employees(dao)
    employees = await t.query(q)

    print("Size: ", len(employees))


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
