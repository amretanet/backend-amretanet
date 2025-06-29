from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime

class BillBase(BaseModel):
    customer_id: str
    amount: float
    status: str = "unpaid"  # 'unpaid', 'paid', 'collected'
    due_date: Optional[datetime]
    note: Optional[str] = None
    receipt_url: Optional[str] = None
    updated_at: Optional[datetime] = None

class BillCreate(BillBase):
    pass

class BillUpdate(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None
    receipt_url: Optional[str] = None
    updated_at: Optional[datetime] = None

class BillInDB(BillBase):
    id: str = Field(..., alias="_id")  # for Mongo ObjectId

class BillStatusData(str, Enum):
    PAID = "PAID"
    UNPAID = "UNPAID"
    PENDING = "PENDING"
    COLLECTING = "COLLECTING"
    COLLECTED = "COLLECTED"

class BillPaymentMethodData(str, Enum):
    CASH = "CASH"
    TRANSFER = "TRANSFER"
    QRIS = "QRIS"
    VIRTUAL_ACCOUNT = "VIRTUAL ACCOUNT"

class BillPayOffData(BaseModel):
    unique_code: int
    method: BillPaymentMethodData
    description: str
    image_url: Optional[str] = None

class RequestConfirmData(BaseModel):
    method: BillPaymentMethodData
    image_url: str
    description: str
