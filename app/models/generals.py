from enum import Enum
from typing import Optional
from pydantic import BaseModel


# schemas
class Pagination(BaseModel):
    page: int = 1
    item: int = 10
    count: int


class GenderData(str, Enum):
    male = "L"
    female = "P"


class Location(BaseModel):
    address: str
    longitude: float
    latitude: float
    image_url: Optional[str] = None


class UploadImageType(str, Enum):
    odc = "odc"
    odp = "odp"
    id_card = "id_card"
    house = "house"
