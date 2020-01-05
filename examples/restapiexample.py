import asyncio
import json
import random
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple

import requests

from restio.dao import BaseDAO
from restio.model import BaseModel, PrimaryKey, mdataclass
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

    def update_employee(self, employee_id: int, employee):
        response = requests.put(self.get_url(f"update/{employee_id}"), employee, headers=self.headers)
        return response.ok

    def _process_response(self, response):
        if response.ok:
            return response.json()

        raise RuntimeError(response)

    def get_url(self, route: str):
        return f"{self.URL}/{route}"


@mdataclass
class Employee(BaseModel):
    id: PrimaryKey[int] = PrimaryKey(int)
    name: str = ""
    age: int = 0
    salary: float = 0.0


class EmployeeDAO(BaseDAO):
    client = ClientAPI()
    pool = ThreadPoolExecutor()

    async def get(self, obj: Tuple[int]) -> Employee:
        loop = asyncio.get_event_loop()
        json = await loop.run_in_executor(self.pool, self.client.get_employee, obj[0])
        return self._get_model(json)

    async def update(self, model: Employee):
        # creates a fictitious error, with 20% chance of failure
        raise_error = random.randint(1, 10) > 8
        if raise_error:
            raise ValueError("Error ocurred during update")

        model_dict = {'name': model.name, 'salary': model.salary, 'age': model.age}
        model_json = json.dumps(model_dict)

        ok = await loop.run_in_executor(
            None, self.client.update_employee, model.id, model_json)

        if not ok:
            raise Exception(f"Error while modifying employee {model.id}.")

    def _get_model(self, json):
        return Employee(
            id=int(json['id']), name=str(json['employee_name']),
            age=int(json['employee_age']), salary=float(json['employee_salary']))


@query
async def get_employees(self, dao: EmployeeDAO) -> List[Employee]:
    # to speed it up, we load only the first 100 employees
    employees = dao.client.get_employees()[:100]
    return [dao._get_model(x) for x in employees]


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

    # gets the primary keys
    employee_ids = [emp.id for emp in employees[:5]]

    # resets the transaction by clearing the cache
    t.reset()

    # retrieves the selected employees from the remote
    # the loop exists to validate the cache only
    employee: Optional[Employee]
    tasks = []
    for employee_id in employee_ids:
        tasks.append(t.get(Employee, employee_id))

    to_modify = []
    for coro in asyncio.as_completed(tasks):
        employee = await coro  # grabs the loaded employee
        to_modify.append(employee)
        print("Manually loaded employee: ", employee)

    # makes a change to be reflected on the server
    for employee in to_modify:
        employee.name = "MyAwesomeName" + str(random.randint(10000, 99999))
        print("Employee persistent cache: ", employee._persistent_values)

    # submits the change to the remote server
    results = await t.commit()

    # we iterate over the results to make sure everything
    # went well
    for dao_task in results:
        try:
            await dao_task
        except Exception:
            # there was an error, so we print the stack
            dao_task.task.print_stack()

    for employee in to_modify:
        print("Employee modified: ", employee)
        print("Employee persistent cache after modifying: ", employee._persistent_values)

    # resets the local cache
    t.reset()

    # reloads the employees from the remote server to verify
    # that the changes were effective
    for employee_id in employee_ids:
        employee = await t.get(Employee, employee_id)
        print("Manually reloaded employee: ", employee)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
