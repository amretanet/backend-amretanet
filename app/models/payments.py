from pydantic import BaseModel
from enum import Enum


# schemas
class PaymentInsertData(BaseModel):
    id_invoice: str
    method: str


class PaymentMethodData(str, Enum):
    TRANSFER = "TRANSFER"
    CASH = "CASH"
