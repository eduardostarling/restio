from itertools import cycle
from typing import List

import pytest

from restio.transaction import Transaction
from tests.integration.employee.client.api import ClientAPI
from tests.integration.employee.client.daos import CompanyDAO, EmployeeDAO
from tests.integration.employee.client.models import Company, Employee
from tests.integration.employee.fixture import CompanyEmployeeFixture
from tests.performance.shared import PerformanceTest


class CompanyEmployeePerformanceFixture(PerformanceTest, CompanyEmployeeFixture):
    async def populate_employees(self, api: ClientAPI, iterations: int):
        for iteration in range(iterations):
            await api.create_employee(
                {"name": f"EmpName{iteration}", "age": 18, "address": "Brazil"}
            )

    @pytest.fixture(scope="function")
    async def employee_keys(self, api: ClientAPI) -> List[str]:
        employees = await api.get_all_employees()
        return [x["key"] for x in employees]

    async def populate_companies(
        self, api: ClientAPI, company_keys: List[str], employee_keys: List[int]
    ):
        company_employee = (
            zip(company_keys, cycle(employee_keys))
            if len(company_keys) > len(employee_keys)
            else zip(cycle(company_keys), employee_keys)
        )

        for company_key, employee_key in company_employee:
            await api.add_employee_to_company(company_key, employee_key)

    @pytest.fixture(scope="function")
    async def company_keys(self, api: ClientAPI) -> List[str]:
        companies = await api.get_all_companies()
        return [x["key"] for x in companies]


class TestPerformanceEmployee(CompanyEmployeePerformanceFixture):
    @pytest.fixture(scope="function", autouse=True)
    async def setup(self, api, iterations):
        await self.populate_employees(api, iterations)

    def test_add_multiple_employees(
        self, benchmark_profile, iterations, transaction: Transaction
    ):
        def wrapper():
            for _ in range(iterations):
                employee = Employee(name="EmpName", age=18, address="Brazil")
                transaction.add(employee)

        benchmark_profile(wrapper)

    @pytest.mark.asyncio
    async def test_get_multiple_employees_one_by_one(
        self, benchmark_profile, employee_keys: List[int], transaction: Transaction,
    ):
        async def wrapper():
            for key in employee_keys:
                await transaction.get(Employee, key=key)

        benchmark_profile(wrapper)

    @pytest.mark.parametrize(
        "iterations", PerformanceTest._iterations(13), indirect=True
    )
    @pytest.mark.asyncio
    async def test_get_multiple_employees_query(
        self, benchmark_profile, transaction: Transaction, employee_dao: EmployeeDAO,
    ):
        async def wrapper():
            q = employee_dao.get_all_employees()
            await transaction.query(q, force=True)

        benchmark_profile(wrapper)


class TestPerformanceCompany(CompanyEmployeePerformanceFixture):
    @pytest.fixture(scope="function", autouse=True)
    async def setup_employees(self, api, iterations):
        await self.populate_employees(api, iterations)

    @pytest.fixture(scope="function", autouse=True)
    async def setup_companies(self, setup_employees, api, company_keys, employee_keys):
        await self.populate_companies(api, company_keys, employee_keys)

    @pytest.mark.asyncio
    async def test_get_multiple_companies_one_by_one(
        self, benchmark_profile, transaction: Transaction, company_keys: List[str]
    ):
        async def wrapper():
            for key in company_keys:
                await transaction.get(Company, key=key)

        benchmark_profile(wrapper)

    @pytest.mark.parametrize(
        "iterations", PerformanceTest._iterations(13), indirect=True
    )
    @pytest.mark.asyncio
    async def test_get_multiple_companies_query(
        self, benchmark_profile, transaction: Transaction, company_dao: CompanyDAO,
    ):
        async def wrapper():
            q = company_dao.get_all_companies()
            await transaction.query(q, force=True)

        benchmark_profile(wrapper)
