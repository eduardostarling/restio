from restio.fields import FrozenSetModelField, FrozenType, IntField, StrField
from restio.model import BaseModel


class Employee(BaseModel):
    key: IntField = IntField(pk=True, allow_none=True, frozen=FrozenType.ALWAYS)
    name: StrField = StrField()
    age: IntField = IntField()
    address: StrField = StrField()

    def __init__(self, *, name: str, age: int, address: str):
        self.name = name
        self.age = age
        self.address = address


class Company(BaseModel):
    key: StrField = StrField(pk=True, frozen=FrozenType.ALWAYS)
    name: StrField = StrField(frozen=FrozenType.ALWAYS)
    employees: FrozenSetModelField = FrozenSetModelField(
        Employee, frozen=FrozenType.CREATE
    )

    def __init__(self, *, key: str, name: str):
        self.key = key
        self.name = name

    def hire_employee(self, employee: Employee):
        self.employees = self.employees.union({employee})

    def fire_employee(self, employee: Employee):
        self.employees = self.employees.difference({employee})
