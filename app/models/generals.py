from enum import Enum
from typing import Optional
from pydantic import BaseModel

# responses
MapsProjections = {
    "_id": 0,
    "lat": "$location.latitude",
    "lng": "$location.longitude",
}


# schemas
class Pagination(BaseModel):
    page: int = 1
    item: int = 10
    count: int


class Gender(str, Enum):
    male = "L"
    female = "P"


class Location(BaseModel):
    address: str
    longitude: float
    latitude: float
    image_url: Optional[str] = None


class Package(BaseModel):
    name: str
    price: int
    category: str
    bandwidth: int
    instalation_price: int = 0
    max_device: int
    description: str


class UploadImageType(str, Enum):
    odc = "odc"
    odp = "odp"
    customer = "customer"
