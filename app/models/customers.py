from typing import Optional
from pydantic import BaseModel, field_validator
from app.models.generals import GenderData
from enum import Enum

# responses
CustomerProjections = {
    "name": 1,
    "service_number": 1,
    "location": 1,
    "created_at": 1,
    "odp_name": 1,
    "email": 1,
    "phone_number": 1,
    "status": 1,
    "ppn": 1,
    "due_date": 1,
    "billing": 1,
    "referral": 1,
    "package": 1,
    "add_on_packages": 1,
    "registered_at": 1,
    "unique_code": 1,
}


# schemas
class CustomerSortingsData(str, Enum):
    NAME = "name"
    SERVICE_NUMBER = "service_number"
    UNIQUE_CODE = "unique_code"
    ODP_NAME = "odp_name"
    DUE_DATE = "due_date"
    REGISTERED_AT = "registered_at"


class CustomerStatusData(int, Enum):
    NONACTIVE = 0
    ACTIVE = 1
    PENDING = 2
    FREE = 3
    ISOLIR = 4
    PAID_LEAVE = 5


class CustomerBillingTypeData(str, Enum):
    PRABAYAR = "PRABAYAR"
    PASCABAYAR = "PASCABAYAR"


class CustomerIDCardData(BaseModel):
    type: str
    number: int
    image_url: Optional[str]


class CustomerLocationData(BaseModel):
    house_status: str
    house_owner: str
    house_image_url: Optional[str] = None
    address: str
    latitude: float
    longitude: float


class CustomerInsertData(BaseModel):
    service_number: int
    name: str
    status: CustomerStatusData
    id_card: CustomerIDCardData
    gender: GenderData
    email: str
    phone_number: str
    location: CustomerLocationData
    description: str
    billing_type: CustomerBillingTypeData
    ppn: int
    due_date: str
    referral: Optional[str] = None
    pppoe_username: str
    pppoe_password: str
    id_router: str
    id_package: str
    id_add_on_package: Optional[list[str]] = []
    id_coverage_area: str
    id_odp: str
    port_odp: int

    @field_validator("name", mode="before")
    @classmethod
    def capitalize_name(cls, value: str) -> str:
        return value.title() if isinstance(value, str) else value


class CustomerUpdateData(BaseModel):
    service_number: int
    name: str
    status: CustomerStatusData
    id_card: CustomerIDCardData
    gender: GenderData
    email: str
    phone_number: str
    location: CustomerLocationData
    description: str
    billing_type: CustomerBillingTypeData
    ppn: int
    due_date: str
    referral: Optional[str] = None
    pppoe_username: str
    pppoe_password: str
    id_router: str
    id_package: str
    id_add_on_package: Optional[list[str]] = []
    id_coverage_area: str
    id_odp: str
    port_odp: int

    @field_validator("name", mode="before")
    @classmethod
    def capitalize_name(cls, value: str) -> str:
        return value.title() if isinstance(value, str) else value


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

    @field_validator("name", mode="before")
    @classmethod
    def capitalize_name(cls, value: str) -> str:
        return value.title() if isinstance(value, str) else value
