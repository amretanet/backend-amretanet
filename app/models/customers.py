from typing import Optional
from pydantic import BaseModel
from app.models.generals import GenderData
from enum import Enum

# responses
CustomerProjections = {
    "name": 1,
    "service_number": 1,
    "location": 1,
    "created_at": 1,
    "odp_name": 1,
    "phone_number": 1,
    "status": 1,
    "ppn": 1,
    "due_date": 1,
    "billing": 1,
    "referral": 1,
}


# schemas
class CustomerStatusData(int, Enum):
    NONACTIVE = 0
    ACTIVE = 1
    PENDING = 2
    FREE = 3
    ISOLIR = 4
    PAID = 5


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


class CustomerUpdateData(BaseModel):
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
    pppoe_username: str
    pppoe_password: str
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
    referral: Optional[str] = None
    id_package: str
    instalation_date: Optional[str] = None
