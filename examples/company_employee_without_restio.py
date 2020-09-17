from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Set

import aiohttp

URL = "http://my-remote-rest-api"

EMPLOYEES_URL = f"{URL}/employees"  # Employees Endpoint
EMPLOYEE_URL = f"{EMPLOYEES_URL}/{{employee_key}}"  # Employee Endpoint

COMPANIES_URL = f"{URL}/companies"  # Companies Endpoint
COMPANY_URL = f"{COMPANIES_URL}/{{company_key}}"  # Company Endpoint

COMPANY_EMPLOYEES_URL = f"{COMPANY_URL}/employees"  # Company Employees Endpoint
COMPANY_EMPLOYEE_URL = (
    f"{COMPANY_EMPLOYEES_URL}/{{employee_key}}"  # Company Employee Endpoint
)

# Models


class Employee:
    key: int
    name: str
    age: int
    address: str

    session: aiohttp.ClientSession = aiohttp.ClientSession(raise_for_status=True)

    def __init__(self, key: int, name: str, age: int, address: str) -> None:
        self.key = key
        self.name = name
        self.age = age
        self.address = address

    @staticmethod
    async def get(employee_key: int) -> Employee:
        url = EMPLOYEE_URL.format(employee_key=employee_key)

        result = await Employee.session.get(url)
        json_data = await result.json()
        return Employee.from_dict(json_data)

    async def update(self):
        url = EMPLOYEE_URL.format(employee_key=self.key)
        payload = json.dumps(self.to_dict())

        await self.session.put(url, data=payload.encode())

    async def create(self):
        url = EMPLOYEES_URL
        payload = json.dumps(self.to_dict())

        response = await self.session.post(url, data=payload.encode())

        # get the key created by the server
        location = response.headers["Location"]
        key = location.split("/")[-1]

        self.key = key

    @staticmethod
    async def get_all() -> Set[Employee]:
        url = EMPLOYEES_URL

        response = await Employee.session.get(url)
        json_data = await response.json()
        return set(Employee.from_dict(e) for e in json_data)

    @staticmethod
    def from_dict(dict_data: Dict[str, Any]) -> Employee:
        return Employee(
            key=dict_data["key"],
            name=dict_data["name"],
            age=dict_data["age"],
            address=dict_data["address"],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "age": self.age, "address": self.address}

    def __hash__(self) -> int:
        return hash(self.key)


class Company:
    key: str
    name: str
    employees: Set[Employee]

    session: aiohttp.ClientSession = aiohttp.ClientSession(raise_for_status=True)

    def __init__(self, key: str, name: str, employees: Set[Employee]) -> None:
        self.key = key
        self.name = name
        self.employees = employees

    @staticmethod
    async def get(company_key: str) -> Company:
        url_company = COMPANY_URL.format(company_key=company_key)

        response = await Company.session.get(url_company)
        json_data = await response.json()

        employees = await Company.get_employees(company_key)

        return Company.from_dict(json_data, employees=employees)

    @staticmethod
    async def get_employees(company_key: str) -> Set[Employee]:
        url_employees = COMPANY_EMPLOYEES_URL.format()

        response = await Company.session.get(url_employees)
        json_data = await response.json()
        return set(Employee.from_dict(e) for e in json_data)

    async def hire_employee(self, employee: Employee):
        url = COMPANY_EMPLOYEE_URL.format(
            company_key=self.key, employee_key=employee.key
        )

        await self.session.put(url)
        self.employees.add(employee)

    @staticmethod
    def from_dict(dict_data: Dict[str, Any], employees: Set[Employee]) -> Company:
        return Company(
            key=dict_data["key"], name=dict_data["name"], employees=employees
        )


async def main():
    joseph = await Employee.get(1000)

    # updates Joseph Tribiani's address
    joseph.address = "New address"
    await joseph.update()

    # loads the Amazing Company A
    company_a = await Company.get("COMPANY_A")

    # hires Chandler Bing, that lives together with Joseph
    chandler = Employee(key=0, name="Chandler Bing", age=26, address=joseph.address)
    await chandler.create()
    await company_a.hire_employee(chandler)


if __name__ == "__main__":
    asyncio.run(main())
