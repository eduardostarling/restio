import asyncio
import json
from typing import Any, Callable, Dict, FrozenSet, List, Tuple

import aiohttp

from restio.dao import BaseDAO
from restio.fields import FrozenSetModelField, FrozenType, IntField, StrField
from restio.model import BaseModel
from restio.query import query
from restio.session import Session


class Employee(BaseModel):
    key: IntField = IntField(pk=True, allow_none=True, frozen=FrozenType.ALWAYS)
    name: StrField = StrField()
    age: IntField = IntField()
    address: StrField = StrField()


class Company(BaseModel):
    key: StrField = StrField(pk=True, frozen=FrozenType.ALWAYS)
    name: StrField = StrField(frozen=FrozenType.ALWAYS)
    employees: FrozenSetModelField = FrozenSetModelField(
        Employee, frozen=FrozenType.CREATE
    )

    def hire_employee(self, employee: Employee):
        self.employees = self.employees.union({employee})


URL = "http://my-remote-rest-api"

EMPLOYEES_URL = f"{URL}/employees"  # Employees Endpoint
EMPLOYEE_URL = f"{EMPLOYEES_URL}/{{employee_key}}"  # Employee Endpoint

COMPANIES_URL = f"{URL}/companies"  # Companies Endpoint
COMPANY_URL = f"{COMPANIES_URL}/{{company_key}}"  # Company Endpoint

COMPANY_EMPLOYEES_URL = f"{COMPANY_URL}/employees"  # Company Employees Endpoint
COMPANY_EMPLOYEE_URL = (
    f"{COMPANY_EMPLOYEES_URL}/{{employee_key}}"  # Company Employee Endpoint
)


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
        # here we could have simply used Employee(**employee_dict) as well
        return Employee(
            key=employee_dict["key"],
            name=employee_dict["name"],
            age=employee_dict["age"],
            address=employee_dict["address"],
        )


class CompanyDAO(BaseDAO[Company]):
    async def get(self, *, key: str) -> Company:
        company_dict = await api.get_company(key)

        # now we load all the employees that belong to the company
        company_employees_query = self.get_company_employees(company_key=key)
        # this will not only retrieve all the company employees, but will also
        # register all the loaded employees to the cache - the `force` argument
        # is used to tell the session to execute the query again, without
        # replacing the models that are already in the cache
        company_employees: Tuple[Employee, ...] = await self.session.query(
            company_employees_query, force=True
        )

        # instantiates the company object
        return self._from_dict(company_dict, frozenset(company_employees))

    @query
    @classmethod
    async def get_company_employees(
        cls, company_key: str, *, session
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

        await asyncio.gather(*tasks)

    @staticmethod
    def _from_dict(
        company_dict: CompanyDict, employees: FrozenSet[Employee]
    ) -> Company:
        return Company(
            key=company_dict["key"], name=company_dict["name"], employees=employees
        )


async def main():
    session = Session()
    session.register_dao(EmployeeDAO(Employee))
    session.register_dao(CompanyDAO(Company))

    # loads Joseph Tribiani
    joseph = await session.get(Employee, key=1000)
    # loads the Amazing Company A
    company_a = await session.get(Company, key="COMPANY_A")

    # updates Joseph Tribiani's address
    joseph.address = "New address"

    # hires Chandler Bing, that lives together with Joseph
    chandler = Employee(name="Chandler Bing", age=26, address=joseph.address)
    session.add(chandler)

    company_a.hire_employee(chandler)

    await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
