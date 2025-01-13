from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from app.models.generals import GenderData

# responses
UserProjections = {
    "_id": 1,
    "name": 1,
    "email": 1,
    "phone_number": 1,
    "status": 1,
    "gender": 1,
    "saldo": 1,
    "referral": 1,
    "role": 1,
    "address": 1,
}


# schemas
class UserStatusData(int, Enum):
    ACTIVE = 1
    NONACTIVE = 0


class UserRole(int, Enum):
    ADMIN = 1
    SALES = 2
    CUSTOMER_SERVICE = 3
    NETWORK_OPERATOR = 4
    ENGINEER = 5
    CUSTOMER = 99


class UserData(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    email: str
    phone_number: Optional[str] = None
    status: Optional[int] = None
    gender: Optional[str] = None
    saldo: Optional[int] = 0
    role: Optional[int] = None
    referral: Optional[str] = None
    address: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class UserInsertData(BaseModel):
    name: str
    email: str
    password: str
    phone_number: Optional[str] = None
    status: UserStatusData = UserStatusData.ACTIVE.value
    gender: GenderData
    saldo: int = 0
    role: UserRole
    address: str


class UserUpdateData(BaseModel):
    name: str
    email: str
    phone_number: Optional[str] = None
    status: UserStatusData = UserStatusData.ACTIVE.value
    gender: GenderData
    saldo: int = 0
    role: UserRole
    address: str


class UserChangePasswordData(BaseModel):
    old_password: str
    new_password: str
    confirm_new_password: str
