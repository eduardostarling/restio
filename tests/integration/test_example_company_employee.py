from typing import Tuple

import pytest

from restio.transaction import Transaction, TransactionException
from tests.integration.employee.client.api import ClientAPI
from tests.integration.employee.client.daos import CompanyDAO, EmployeeDAO
from tests.integration.employee.client.models import Company, Employee
from tests.integration.employee.fixture import CompanyEmployeeFixture


class TestIntegrationCompanyEmployee(CompanyEmployeeFixture):
    @pytest.mark.asyncio
    async def test_get_employee(self, transaction: Transaction):
        employee = await transaction.get(Employee, key=1000)

        assert employee.key == 1000
        assert employee.name == "Joseph Tribiani"
        assert employee.age == 25
        assert employee.address == "1 Granville St, Vancouver, BC, VXX XXX, Canada"

    @pytest.mark.asyncio
    async def test_get_all_employees(
        self, transaction: Transaction, employee_dao: EmployeeDAO
    ):
        q = employee_dao.get_all_employees()
        all_employees: Tuple[Employee, ...] = await transaction.query(q)

        assert len(all_employees) == 3
        assert set(e.key for e in all_employees) == {1000, 1001, 1002}

    @pytest.mark.asyncio
    async def test_get_employee_that_doesnt_exist(self, transaction: Transaction):
        with pytest.raises(ValueError):
            await transaction.get(Employee, key=5555)

    @pytest.mark.asyncio
    async def test_get_company(self, transaction: Transaction):
        company = await transaction.get(Company, key="COMPANY_A")

        assert company.key == "COMPANY_A"
        assert company.name == "Amazing Company A"
        assert company.employees

    @pytest.mark.asyncio
    async def test_get_all_companies(
        self, transaction: Transaction, company_dao: CompanyDAO
    ):
        q = company_dao.get_all_companies()
        companies: Tuple[Company, ...] = await transaction.query(q)

        assert len(companies) == 2
        assert sum(len(c.employees) for c in companies) == 2

    @pytest.mark.asyncio
    async def test_get_company_that_doesnt_exist(self, transaction: Transaction):
        with pytest.raises(ValueError):
            await transaction.get(Company, key="COMPANY_5555")

    @pytest.mark.asyncio
    async def test_get_company_before_employee(self, transaction: Transaction):
        company = await transaction.get(Company, key="COMPANY_A")
        employee = await transaction.get(Employee, key=1000)

        assert company.employees == frozenset({employee})

    @pytest.mark.asyncio
    async def test_get_company_after_employee(self, transaction: Transaction):
        employee = await transaction.get(Employee, key=1000)
        company = await transaction.get(Company, key="COMPANY_A")

        assert company.employees == frozenset({employee})

    @pytest.mark.asyncio
    async def test_create_employee(
        self,
        transaction: Transaction,
        api: ClientAPI,
        employee_dao: EmployeeDAO,
        company_dao: CompanyDAO,
    ):
        new_employee = Employee(name="Chandler Bing", age=26, address="California")
        transaction.add(new_employee)
        assert new_employee.key is None

        await transaction.commit()

        assert new_employee.key is not None

        new_transaction = self._get_transaction(api, employee_dao, company_dao)
        added_employee = await new_transaction.get(Employee, key=new_employee.key)

        assert added_employee.name == new_employee.name
        assert added_employee.age == new_employee.age
        assert added_employee.address == new_employee.address

    @pytest.mark.asyncio
    async def test_create_and_hire_employee(self, transaction: Transaction):
        new_employee = Employee(name="Chandler Bing", age=26, address="California")
        company = await transaction.get(Company, key="COMPANY_B")
        transaction.add(new_employee)

        company.hire_employee(new_employee)

        assert new_employee.key is None
        assert new_employee in company.employees

        await transaction.commit()

        assert new_employee.key is not None
        assert new_employee in company.employees

    @pytest.mark.asyncio
    async def test_create_employe_but_hire_before_creating(
        self, transaction: Transaction
    ):
        new_employee = Employee(name="Chandler Bing", age=26, address="California")
        company = await transaction.get(Company, key="COMPANY_B")

        with pytest.raises(ValueError):
            company.hire_employee(new_employee)

        assert new_employee not in company.employees

    @pytest.mark.asyncio
    async def test_update_employee_address(
        self,
        transaction: Transaction,
        api: ClientAPI,
        employee_dao: EmployeeDAO,
        company_dao: CompanyDAO,
    ):
        employee = await transaction.get(Employee, key=1000)
        assert employee.address != "Brazil"

        employee.address = "Brazil"
        await transaction.commit()

        new_transaction = self._get_transaction(api, employee_dao, company_dao)
        updated_employee = await new_transaction.get(Employee, key=1000)

        assert updated_employee != employee
        assert updated_employee.address == "Brazil"

    @pytest.mark.asyncio
    async def test_remove_employee(self, transaction: Transaction):
        employee = await transaction.get(Employee, key=1002)
        transaction.remove(employee)

        await transaction.commit()

        with pytest.raises(ValueError):
            await transaction.get(Employee, key=1002)

    @pytest.mark.asyncio
    async def test_remove_employee_without_firing_and_no_company_in_cache(
        self, transaction: Transaction, employee_dao: EmployeeDAO
    ):
        employee = await transaction.get(Employee, key=1000)
        transaction.remove(employee)

        with pytest.raises(TransactionException):
            await transaction.commit()

        q = employee_dao.get_all_employees()
        all_employees = await transaction.query(q)

        assert employee in all_employees

    @pytest.mark.asyncio
    async def test_remove_employee_without_firing_with_company_in_cache(
        self, transaction: Transaction
    ):
        company = await transaction.get(Company, key="COMPANY_A")
        employee = await transaction.get(Employee, key=1000)

        assert employee in company.employees

        transaction.remove(employee)

        with pytest.raises(RuntimeError):
            await transaction.commit()

    @pytest.mark.asyncio
    async def test_fire_and_remove_employee(
        self, transaction: Transaction, employee_dao: EmployeeDAO
    ):
        company = await transaction.get(Company, key="COMPANY_A")
        employee = await transaction.get(Employee, key=1000)
        company.fire_employee(employee)
        transaction.remove(employee)

        await transaction.commit()

        q = employee_dao.get_all_employees()
        all_employees = await transaction.query(q)

        assert employee not in all_employees
