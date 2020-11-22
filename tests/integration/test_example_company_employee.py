from typing import Tuple

import pytest

from restio.session import Session, SessionException
from tests.integration.employee.client.api import ClientAPI
from tests.integration.employee.client.daos import CompanyDAO, EmployeeDAO
from tests.integration.employee.client.models import Company, Employee
from tests.integration.employee.fixture import CompanyEmployeeFixture


class TestIntegrationCompanyEmployee(CompanyEmployeeFixture):
    @pytest.mark.asyncio
    async def test_get_employee(self, session: Session):
        employee = await session.get(Employee, key=1000)

        assert employee.key == 1000
        assert employee.name == "Joseph Tribiani"
        assert employee.age == 25
        assert employee.address == "1 Granville St, Vancouver, BC, VXX XXX, Canada"

    @pytest.mark.asyncio
    async def test_get_all_employees(self, session: Session, employee_dao: EmployeeDAO):
        q = employee_dao.get_all_employees()
        all_employees: Tuple[Employee, ...] = await session.query(q)

        assert len(all_employees) == 3
        assert set(e.key for e in all_employees) == {1000, 1001, 1002}

    @pytest.mark.asyncio
    async def test_get_employee_that_doesnt_exist(self, session: Session):
        with pytest.raises(ValueError):
            await session.get(Employee, key=5555)

    @pytest.mark.asyncio
    async def test_get_company(self, session: Session):
        company = await session.get(Company, key="COMPANY_A")

        assert company.key == "COMPANY_A"
        assert company.name == "Amazing Company A"
        assert company.employees

    @pytest.mark.asyncio
    async def test_get_all_companies(self, session: Session, company_dao: CompanyDAO):
        q = company_dao.get_all_companies()
        companies: Tuple[Company, ...] = await session.query(q)

        assert len(companies) == 2
        assert sum(len(c.employees) for c in companies) == 2

    @pytest.mark.asyncio
    async def test_get_company_that_doesnt_exist(self, session: Session):
        with pytest.raises(ValueError):
            await session.get(Company, key="COMPANY_5555")

    @pytest.mark.asyncio
    async def test_get_company_before_employee(self, session: Session):
        company = await session.get(Company, key="COMPANY_A")
        employee = await session.get(Employee, key=1000)

        assert company.employees == frozenset({employee})

    @pytest.mark.asyncio
    async def test_get_company_after_employee(self, session: Session):
        employee = await session.get(Employee, key=1000)
        company = await session.get(Company, key="COMPANY_A")

        assert company.employees == frozenset({employee})

    @pytest.mark.asyncio
    async def test_create_employee(
        self,
        session: Session,
        api: ClientAPI,
        employee_dao: EmployeeDAO,
        company_dao: CompanyDAO,
    ):
        new_employee = Employee(name="Chandler Bing", age=26, address="California")
        session.add(new_employee)
        assert new_employee.key is None

        await session.commit()

        assert new_employee.key is not None

        new_session = self._get_session(api, employee_dao, company_dao)
        added_employee = await new_session.get(Employee, key=new_employee.key)

        assert added_employee.name == new_employee.name
        assert added_employee.age == new_employee.age
        assert added_employee.address == new_employee.address

    @pytest.mark.asyncio
    async def test_create_young_employee(
        self, session: Session,
    ):
        with pytest.raises(ValueError, match="younger than 18"):
            Employee(name="Young Employee", age=15, address="California")

    @pytest.mark.asyncio
    async def test_create_and_hire_employee(self, session: Session):
        new_employee = Employee(name="Chandler Bing", age=26, address="California")
        company = await session.get(Company, key="COMPANY_B")
        session.add(new_employee)

        company.hire_employee(new_employee)

        assert new_employee.key is None
        assert new_employee in company.employees

        await session.commit()

        assert new_employee.key is not None
        assert new_employee in company.employees

    @pytest.mark.asyncio
    async def test_create_employe_but_hire_before_creating(self, session: Session):
        new_employee = Employee(name="Chandler Bing", age=26, address="California")
        company = await session.get(Company, key="COMPANY_B")

        with pytest.raises(ValueError):
            company.hire_employee(new_employee)

        assert new_employee not in company.employees

    @pytest.mark.asyncio
    async def test_update_employee_address(
        self,
        session: Session,
        api: ClientAPI,
        employee_dao: EmployeeDAO,
        company_dao: CompanyDAO,
    ):
        employee = await session.get(Employee, key=1000)
        assert employee.address != "Brazil"

        employee.address = "Brazil"
        await session.commit()

        new_session = self._get_session(api, employee_dao, company_dao)
        updated_employee = await new_session.get(Employee, key=1000)

        assert updated_employee != employee
        assert updated_employee.address == "Brazil"

    @pytest.mark.asyncio
    async def test_remove_employee(self, session: Session):
        employee = await session.get(Employee, key=1002)
        session.remove(employee)

        await session.commit()

        with pytest.raises(ValueError):
            await session.get(Employee, key=1002)

    @pytest.mark.asyncio
    async def test_remove_employee_without_firing_and_no_company_in_cache(
        self, session: Session, employee_dao: EmployeeDAO
    ):
        employee = await session.get(Employee, key=1000)
        session.remove(employee)

        with pytest.raises(SessionException):
            await session.commit()

        q = employee_dao.get_all_employees()
        all_employees = await session.query(q)

        assert employee in all_employees

    @pytest.mark.asyncio
    async def test_remove_employee_without_firing_with_company_in_cache(
        self, session: Session
    ):
        company = await session.get(Company, key="COMPANY_A")
        employee = await session.get(Employee, key=1000)

        assert employee in company.employees

        session.remove(employee)

        with pytest.raises(RuntimeError):
            await session.commit()

    @pytest.mark.asyncio
    async def test_fire_and_remove_employee(
        self, session: Session, employee_dao: EmployeeDAO
    ):
        company = await session.get(Company, key="COMPANY_A")
        employee = await session.get(Employee, key=1000)
        company.fire_employee(employee)
        session.remove(employee)

        await session.commit()

        q = employee_dao.get_all_employees()
        all_employees = await session.query(q)

        assert employee not in all_employees
