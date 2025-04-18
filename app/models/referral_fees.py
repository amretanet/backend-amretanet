from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from enum import Enum

# responses
ReferralFeeProjections = {
    "name": "$user_data.name",
    "email": "$user_data.email",
    "phone_number": "$user_data.phone_number",
    "referral": "$user_data.referral",
    "saldo": "$user_data.saldo",
    "id_user": "$user_data._id",
    "created_at": 1,
    "date": 1,
    "nominal": 1,
    "status": 1,
    "description": 1,
    "reason": 1,
}
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
class ReferralFeeStatusData(str, Enum):
    ACCEPTED = "ACCEPTED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class ReferralFeePayoffData(BaseModel):
    id_user: str
    date: datetime
    nominal: int
    description: str
    method: str


class ReferralFeeUpdateData(BaseModel):
    status: Optional[ReferralFeeStatusData] = None
    date: Optional[datetime] = None
    nominal: Optional[int] = None
    description: Optional[str] = None
    method: Optional[str] = None
