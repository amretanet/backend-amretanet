from enum import Enum
from typing import Optional
from pydantic import BaseModel


# schemas
class Pagination(BaseModel):
    page: int = 1
    item: int = 10
    count: int


class GenderData(str, Enum):
    MALE = "L"
    FEMALE = "P"


class Location(BaseModel):
    address: Optional[str] = None
    longitude: float
    latitude: float
    image_url: Optional[str] = None


class UploadImageType(str, Enum):
    payment_evidence = "payment_evidence"
    odc_attachment = "odc_attachment"
    odp_attachment = "odp_attachment"
    id_card_attachment = "id_card_attachment"
    house_attachment = "house_attachment"
    ticket_attachment = "ticket_attachment"
    utils = "utils"
