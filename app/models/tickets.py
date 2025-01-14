from typing import Optional
from pydantic import BaseModel
from enum import Enum
from app.models.generals import Location

# responses
TicketProjections = {
    "name": 1,
    "address": 1,
    "capacity": 1,
    "available": 1,
}


# schema
class TicketEpidenceData(BaseModel):
    odp_image_url: Optional[str] = None
    ont_image_url: Optional[str] = None
    ont_position_image_url: Optional[str] = None
    seriel_number_image_url: Optional[str] = None
    house_image_url: Optional[str] = None
    customer_image_url: Optional[str] = None
    other_image_url: Optional[str] = None


class TicketStatusData(str, Enum):
    OPEN = "OPEN"
    PENDING = "PENDING"
    ON_PROGRESS = "ON_PROGRESS"
    CLOSED = "CLOSED"


class TicketTypeData(str, Enum):
    FOM = "FOM"
    PSB = "PSB"
    TKT = "TKT"


class TicketInsertData(BaseModel):
    id_reporter: Optional[str] = None
    id_assignee: Optional[str] = None
    id_odc: Optional[str] = None
    id_odp: Optional[str] = None
    title: str
    description: str
    type: TicketTypeData


class TicketUpdateData(BaseModel):
    id_reporter: Optional[str] = None
    id_assignee: Optional[str] = None
    id_odc: Optional[str] = None
    id_odp: Optional[str] = None
    title: Optional[str] = None
    type: Optional[TicketTypeData] = None
    description: Optional[str] = None
    status: Optional[TicketStatusData] = None


class TicketCloseData(BaseModel):
    id_odc: Optional[str] = None
    id_odp: Optional[str] = None
    tube: Optional[str] = None
    cable: Optional[int] = None
    hardware: Optional[str] = None
    serial_number: Optional[str] = None
    re_odp: Optional[int] = None
    re_ont: Optional[int] = None
    evidence: TicketEpidenceData
    location: Location
    confirm_message: str
