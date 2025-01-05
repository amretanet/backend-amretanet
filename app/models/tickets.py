from typing import Optional
from pydantic import BaseModel
from enum import Enum


# schema
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
