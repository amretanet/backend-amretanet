from typing import Optional
from pydantic import BaseModel
from enum import Enum


# schemas
class ChangeSubmissionTypeData(str, Enum):
    PPPOE = "PPPOE"
    ADD_ONS = "ADD-ONS"


class ChangeSubmissionStatusData(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ChangeSubmissionInsertData(BaseModel):
    type: ChangeSubmissionTypeData
    id_package: str
    id_customer: str
    reason_message: str


class ChangeSubmissionUpdateData(BaseModel):
    type: Optional[ChangeSubmissionTypeData] = None
    id_package: Optional[str] = None
    id_customer: Optional[str] = None
    status: Optional[ChangeSubmissionStatusData] = None
    reason_message: Optional[str] = None
    confirm_message: Optional[str] = None
