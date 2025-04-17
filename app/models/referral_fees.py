from datetime import datetime
from pydantic import BaseModel
from enum import Enum

# responses
ReferralFeeUserProjections = {
    "name": 1,
    "email": 1,
    "phone_number": 1,
    "role": 1,
    "referral": 1,
    "saldo": 1,
    "customer_count": 1,
}


# schemas
class ReferralFeePayoffData(BaseModel):
    id_user: str
    date: datetime
    nominal: int
    description: str
    method: str


class ReferralFeeStatusData(str, Enum):
    ACCEPTED = "ACCEPTED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"
