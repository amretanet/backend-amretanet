from typing import Optional
from enum import Enum
from pydantic import BaseModel
from app.models.payments import PaymentMethodData


# schemas
class SalaryStatusData(str, Enum):
    PAID = "PAID"
    PENDING = "PENDING"
    UNPAID = "UNPAID"


class SalaryAbsenceData(BaseModel):
    days_present: int
    days_late: int
    days_sick: int
    days_on_leave: int
    days_absent: int


class SalaryPeriodeData(BaseModel):
    month: str
    year: int


class SalaryInsertData(BaseModel):
    id_user: str
    period: SalaryPeriodeData
    basic_salary: int
    overtime_allowance: int
    transport_allowance: int
    bpjs_allowance: int
    other_allowance: int
    cash_deduction: int
    bpjs_deduction: int
    absent_deduction: int
    other_deduction: int
    salary: int
    status: SalaryStatusData
    method: Optional[PaymentMethodData]
    absence_summary: SalaryAbsenceData
    description: str


class SalaryUpdateData(BaseModel):
    id_user: Optional[str]
    period: Optional[SalaryPeriodeData]
    basic_salary: Optional[int]
    overtime_allowance: Optional[int]
    transport_allowance: Optional[int]
    bpjs_allowance: Optional[int]
    other_allowance: Optional[int]
    cash_deduction: Optional[int]
    bpjs_deduction: Optional[int]
    absent_deduction: Optional[int]
    other_deduction: Optional[int]
    salary: Optional[int]
    status: Optional[SalaryStatusData]
    method: Optional[PaymentMethodData]
    absence_summary: Optional[SalaryAbsenceData]
    description: Optional[str]
