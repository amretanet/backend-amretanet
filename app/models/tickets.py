from typing import Optional
from pydantic import BaseModel
from enum import Enum
from app.models.generals import Location


# schema
class TicketEpidenceData(BaseModel):
    odp_image_url: Optional[str] = None
    ont_image_url: Optional[str] = None
    ont_position_image_url: Optional[str] = None
    seriel_number_image_url: Optional[str] = None
    house_image_url: Optional[str] = None
    customer_image_url: Optional[str] = None
    other_image_url: Optional[str] = None
    pending_image_url: Optional[str] = None


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


class TicketPreconData(BaseModel):
    id: Optional[str] = None
    quantity: Optional[int] = None


class TicketONTData(BaseModel):
    id: Optional[str] = None
    quantity: Optional[int] = None
    serial_number: Optional[str] = None


class TicketCloseData(BaseModel):
    id_odc: Optional[str] = None
    id_odp: Optional[str] = None
    tube: Optional[str] = None
    ont: Optional[TicketONTData] = None
    precon: Optional[TicketPreconData] = None
    re_odp: Optional[int] = None
    re_ont: Optional[int] = None
    evidence: TicketEpidenceData
    location: Location
    confirm_message: str


class TicketPendingData(BaseModel):
    confirm_message: str
    evidence: TicketEpidenceData
