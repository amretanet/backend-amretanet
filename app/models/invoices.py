from enum import Enum
from typing import Optional
from pydantic import BaseModel


# schemas
class InvoiceStatusData(str, Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    PENDING = "PENDING"


class InvoiceUpdateData(BaseModel):
    id_invoice: str
    id_customer: str
    id_package: str
    id_add_on_package: Optional[list[str]]
