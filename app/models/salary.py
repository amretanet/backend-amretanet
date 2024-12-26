from datetime import datetime
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
    gross_salary: int
    deductions: int
    bonuses: int
    net_salary: int
    status: SalaryStatusData
    method: Optional[PaymentMethodData]
    absence_summary: SalaryAbsenceData
    description: str


class SalaryUpdateData(BaseModel):
    id_user: Optional[str]
    period: Optional[SalaryPeriodeData]
    gross_salary: Optional[int]
    deductions: Optional[int]
    bonuses: Optional[int]
    net_salary: Optional[int]
    status: Optional[SalaryStatusData]
    method: Optional[PaymentMethodData]
    absence_summary: Optional[SalaryAbsenceData]
    description: Optional[str]
