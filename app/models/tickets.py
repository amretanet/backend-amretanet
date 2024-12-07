from typing import Optional
from pydantic import BaseModel
from enum import Enum


# schema
class TicketStatusData(str, Enum):
    open = ("open",)
    pending = "pending"
    on_progress = "on_progress"
    closed = "closed"


class TicketInsertData(BaseModel):
    id_reporter: str
    id_assignee: str
    id_odc: Optional[str] = None
    id_odp: Optional[str] = None
    title: str
    description: str


class TicketUpdateData(BaseModel):
    id_reporter: Optional[str] = None
    id_assignee: Optional[str] = None
    id_odc: Optional[str] = None
    id_odp: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TicketStatusData] = None
