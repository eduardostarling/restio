import asyncio
import random
from functools import partial
from typing import Any, Dict, List, TypeVar

from flask.testing import FlaskClient

URL = ""

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

CallableMethod = TypeVar("CallableMethod")


class ClientAPI:
    client: FlaskClient

    def __init__(self, client: FlaskClient):
        self.client = client

    # Employees Endpoints

    async def get_employee(self, key: int) -> EmployeeDict:
        url = EMPLOYEE_URL.format(employee_key=key)
        response = await self._async(self.client.get, url)
        if response.status_code == 404:
            raise ValueError("Employee not found.")
        return response.get_json()

    async def create_employee(self, employee: EmployeeDict) -> int:
        response = await self._async(self.client.post, EMPLOYEES_URL, json=employee)
        if response.status_code != 201:
            raise ValueError("Can't create Employee.")

        location = response.headers["Location"]
        key = location.split("/")[-1]

        return int(key)

    async def update_employee(self, key: int, employee: EmployeeDict):
        url = EMPLOYEE_URL.format(employee_key=key)
        response = await self._async(self.client.put, url, json=employee)
        if response.status_code != 204:
            raise ValueError("Can't update employee.")

    async def remove_employee(self, key: int):
        url = EMPLOYEE_URL.format(employee_key=key)
        response = await self._async(self.client.delete, url)
        if response.status_code != 204:
            raise ValueError("Can't remove employee.")

    async def get_all_employees(self) -> List[EmployeeDict]:
        response = await self._async(self.client.get, EMPLOYEES_URL)
        return response.get_json()

    # Company Endpoints

    async def get_company(self, key: str) -> CompanyDict:
        url = COMPANY_URL.format(company_key=key)
        response = await self._async(self.client.get, url)
        if response.status_code == 404:
            raise ValueError("Company not found.")
        return response.get_json()

    async def get_all_companies(self) -> List[CompanyDict]:
        response = await self._async(self.client.get, COMPANIES_URL)
        return response.get_json()

    # Company Employee Endpoints

    async def get_company_employees(self, company_key: str) -> List[EmployeeDict]:
        url = COMPANY_EMPLOYEES_URL.format(company_key=company_key)
        response = await self._async(self.client.get, url)
        if response.status_code == 404:
            raise ValueError("Company not found.")
        return response.get_json()

    async def add_employee_to_company(self, company_key: str, employee_key: int):
        url = COMPANY_EMPLOYEE_URL.format(
            company_key=company_key, employee_key=employee_key
        )
        response = await self._async(self.client.put, url)
        if response.status_code != 204:
            raise ValueError("Can't add Employee to Company.")

    async def remove_employee_from_company(self, company_key: str, employee_key: int):
        url = COMPANY_EMPLOYEE_URL.format(
            company_key=company_key, employee_key=employee_key
        )
        response = await self._async(self.client.delete, url)
        if response.status_code != 204:
            raise ValueError("Can't remove Employee from Company.")

    async def _async(
        self, method: CallableMethod, *args, delay: bool = True, **kwargs
    ) -> CallableMethod:
        # fakes network delay, 50-100ms
        if delay:
            await asyncio.sleep(random.randint(50, 100) / 1000)
        return await asyncio.get_event_loop().run_in_executor(
            None, partial(method, *args, **kwargs)
        )
