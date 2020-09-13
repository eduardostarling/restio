import asyncio
from typing import Any, Callable, FrozenSet, List

from restio.dao import BaseDAO
from restio.query import query
from tests.integration.employee.client.api import ClientAPI, CompanyDict, EmployeeDict
from tests.integration.employee.client.models import Company, Employee


class EmployeeDAO(BaseDAO[Employee]):
    api: ClientAPI

    def __init__(self, api: ClientAPI):
        super().__init__(Employee)
        self.api = api

    async def get(self, *, key: int) -> Employee:
        employee_dict = await self.api.get_employee(key)
        return self._from_dict(employee_dict)

    async def add(self, obj: Employee):
        key = await self.api.create_employee(self._to_dict(obj))
        obj.key = key

    async def update(self, obj: Employee):
        await self.api.update_employee(obj.key, self._to_dict(obj))

    async def remove(self, obj: Employee):
        await self.api.remove_employee(obj.key)

    @query
    async def get_all_employees(self) -> List[Employee]:
        return [self._from_dict(e) for e in await self.api.get_all_employees()]

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


class CompanyDAO(BaseDAO[Company]):
    api: ClientAPI

    def __init__(self, api: ClientAPI):
        super().__init__(Company)
        self.api = api

    async def get(self, *, key: str) -> Company:
        company_dict = await self.api.get_company(key)
        company = self._from_dict(company_dict)

        company_employees_query = self.get_company_employees(company_key=key)
        company_employees = await self.transaction.query(
            company_employees_query, force=True
        )

        company.employees = frozenset(company_employees)

        return company

    @query
    async def get_all_companies(self) -> List[Company]:
        companies = [self._from_dict(e) for e in await self.api.get_all_companies()]
        employee_tasks = []

        for company in companies:
            company_employees_query = self.get_company_employees(
                company_key=company.key
            )
            company_employees_coro = self.transaction.query(
                company_employees_query, force=True
            )
            employee_tasks.append(asyncio.create_task(company_employees_coro))

        results = await asyncio.gather(*employee_tasks)
        for company, employees in zip(companies, results):
            company.employees = frozenset(employees)

        return companies

    @query
    async def get_company_employees(self, company_key: str) -> FrozenSet[Employee]:
        employees_list = await self.api.get_company_employees(company_key)
        return frozenset(EmployeeDAO._from_dict(e) for e in employees_list)

    async def update(self, obj: Company):
        added_employees: FrozenSet[Employee] = frozenset()
        removed_employees: FrozenSet[Employee] = frozenset()

        if obj.is_field_modified("employees"):
            added_employees = obj.employees - obj._persistent_values["employees"]
            removed_employees = obj._persistent_values["employees"] - obj.employees

        await asyncio.gather(
            self._add_employees(obj, added_employees),
            self._remove_employees(obj, removed_employees),
        )

    async def _add_employees(self, company: Company, employees: FrozenSet[Employee]):
        await self._gather_tasks(company, employees, self.api.add_employee_to_company)

    async def _remove_employees(self, company: Company, employees: FrozenSet[Employee]):
        await self._gather_tasks(
            company, employees, self.api.remove_employee_from_company
        )

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
    def _from_dict(company_dict: CompanyDict) -> Company:
        return Company(key=company_dict["key"], name=company_dict["name"])
