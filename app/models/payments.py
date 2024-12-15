from typing import Optional
from pydantic import BaseModel
from enum import Enum


# schemas


class PaymentMethodData(str, Enum):
    CASH = "CASH"
    TRANSFER = "TRANSFER"
    QRIS = "QRIS"
    VIRTUAL_ACCOUNT = "VIRTUAL ACCOUNT"


class PaymentPayOffData(BaseModel):
    method: PaymentMethodData
    image_url: Optional[str] = None
    description: str


class PaymentVAInsertData(BaseModel):
    id_invoice: str
    method: str


class RequestConfirmData(BaseModel):
    method: PaymentMethodData
    image_url: str
    description: str
