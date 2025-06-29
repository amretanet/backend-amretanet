from enum import Enum
from typing import Optional
from pydantic import BaseModel


# schemas
class InvoiceSortingsData(str, Enum):
    NAME = "name"
    SERVICE_NUMBER = "service_number"
    AMOUNT = "amount"
    DUE_DATE = "due_date"


class InvoiceStatusData(str, Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    PENDING = "PENDING"
    COLLECTING = "COLLECTING"
    COLLECTED = "COLLECTED"


class InvoiceInsertData(BaseModel):
    id_customer: str
    month: str
    year: str


class InvoiceUpdateData(BaseModel):
    id_invoice: str
    id_customer: str
    id_package: str
    id_add_on_package: Optional[list[str]]
