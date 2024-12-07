from typing import Optional
from pydantic import BaseModel
from app.models.generals import GenderData
from enum import Enum


# schemas
class CustomerStatusData(int, Enum):
    nonactive = 0
    active = 1
    pending = 2
    free = 3
    isolir = 4
    paid = 5


class CustomerBillingTypeData(str, Enum):
    PRABAYAR = "PRABAYAR"
    PASCABAYAR = "PASCABAYAR"


class CustomerIDCardData(BaseModel):
    type: str
    number: str
    image_url: Optional[str]


class CustomerLocationData(BaseModel):
    house_status: str
    house_owner: str
    address: str
    latitude: float
    longitude: float


class CustomerInsertData(BaseModel):
    name: str
    id_card: CustomerIDCardData
    gender: GenderData
    email: str
    phone_number: str
    location: CustomerLocationData
    description: str
    billing_type: CustomerBillingTypeData
    ppn: int
    due_date: str
    referral: Optional[int] = 0
    id_router: str
    id_package: str
    id_add_on_package: Optional[list[str]] = []
    id_coverage_area: str
    id_odp: str
    port_odp: int


class CustomerRegisterData(BaseModel):
    name: str
    id_card: CustomerIDCardData
    gender: GenderData
    email: str
    phone_number: str
    location: CustomerLocationData
    referral: Optional[int] = 0
    id_package: str
    instalation_date: Optional[str] = None
