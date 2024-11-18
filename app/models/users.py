from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from app.models.generals import Gender

# responses
UserProjections = {
    "_id": 1,
    "name": 1,
    "email": 1,
    "phone_number": 1,
    "status": 1,
    "gender": 1,
    "saldo": 1,
    "role": 1,
    "address": 1,
}


# schemas
class UserRole(int, Enum):
    admin = 1
    member_ppoe = 2
    member_hotspot = 3
    reseler_hotspot = 4
    sales_ppoe = 5
    network_operator = 6
    customer_service = 7
    employee = 8
    member_premium = 9
    bill_collector = 10


class UserData(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    email: str
    phone_number: Optional[str] = None
    status: Optional[int] = None
    gender: Optional[str] = None
    saldo: Optional[int] = 0
    role: Optional[int] = None
    address: Optional[str] = None

    class Config:
        allow_population_by_field_name = True


class UserInsertData(BaseModel):
    name: str
    email: str
    password: str
    phone_number: Optional[str] = None
    status: int = 1
    gender: Gender
    saldo: int = 0
    role: UserRole
    address: str


class UserUpdateData(BaseModel):
    name: str
    email: str
    phone_number: Optional[str] = None
    status: int = 1
    gender: Gender
    saldo: int = 0
    role: UserRole
    address: str


class UserChangePasswordData(BaseModel):
    old_password: str
    new_password: str
    confirm_new_password: str
