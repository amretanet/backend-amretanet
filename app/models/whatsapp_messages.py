from typing import Optional
from pydantic import BaseModel
from enum import Enum


# schemas
class SendMessageType(str, Enum):
    broadcast = "broadcast"
    single = "single"


class SendMessageData(BaseModel):
    type: SendMessageType
    broadcast_to: Optional[str]
    single_to: Optional[str]
    title: str
    message: str


class AdvanceMessageTemplateData(BaseModel):
    header: Optional[str] = None
    body: Optional[str] = None
    footer: Optional[str] = None
    thanks_message: Optional[str] = None
    thanks_image: Optional[str] = None
    isolir_image: Optional[str] = None
    unique_code_status: Optional[int] = 0
    unique_code_message: Optional[str] = None
    saldo_fee: Optional[int] = 0
