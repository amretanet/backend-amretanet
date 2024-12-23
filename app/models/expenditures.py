from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# schemas
class ExpenditureInsertData(BaseModel):
    nominal: int
    category: str
    method: str
    date: datetime
    description: str


class ExpenditureUpdateData(BaseModel):
    nominal: Optional[int] = None
    category: Optional[str] = None
    method: Optional[str] = None
    date: Optional[datetime] = None
    description: Optional[str] = None
