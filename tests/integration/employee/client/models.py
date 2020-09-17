from restio.fields import FrozenSetModelField, FrozenType, IntField, StrField
from restio.model import BaseModel


class Employee(BaseModel):
    key: IntField = IntField(pk=True, allow_none=True, frozen=FrozenType.ALWAYS)
    name: StrField = StrField()
    age: IntField = IntField()
    address: StrField = StrField()

    @age.setter
    def _validate_age(self, age: int) -> int:
        if age < 18:
            raise ValueError("Cannot have employees younger than 18.")
        return age


class Company(BaseModel):
    key: StrField = StrField(pk=True, frozen=FrozenType.ALWAYS)
    name: StrField = StrField(frozen=FrozenType.ALWAYS)
    employees: FrozenSetModelField = FrozenSetModelField(
        Employee, frozen=FrozenType.CREATE
    )

    def hire_employee(self, employee: Employee):
        self.employees = self.employees.union({employee})

    def fire_employee(self, employee: Employee):
        self.employees = self.employees.difference({employee})
