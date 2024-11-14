from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

# responses
UserProjections = {
    "_id": 1,
    "name": 1,
    "username": 1,
    "email": 1,
    "phone_number": 1,
    "role": 1,
    "status": 1,
}


# schemas
class UserRole(int, Enum):
    admin = 1
    user = 2


class UserData(BaseModel):
    id: str = Field(..., alias="_id")
    name: str
    username: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    role: Optional[int] = None
    status: Optional[int] = None

    class Config:
        allow_population_by_field_name = True


class UserInsertData(BaseModel):
    name: str
    username: str
    password: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    role: UserRole
    status: int = 1


class UserUpdateData(BaseModel):
    name: str
    username: str
    email: Optional[str] = None
    role: UserRole


class UserChangePasswordData(BaseModel):
    old_password: str
    new_password: str
    confirm_new_password: str
