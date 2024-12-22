from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# schemas
class IncomeInsertData(BaseModel):
    id_invoice: Optional[str] = None
    nominal: int
    category: str
    method: str
    date: datetime
    id_receiver: str
    description: str


class IncomeUpdateData(BaseModel):
    id_invoice: Optional[str] = None
    nominal: Optional[int] = None
    category: Optional[str] = None
    method: Optional[str] = None
    date: Optional[datetime] = None
    id_receiver: Optional[str] = None
    description: Optional[str] = None
