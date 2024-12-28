from typing import Optional
from pydantic import BaseModel


# schemas
class MikrotikUpdateData(BaseModel):
    router: str
    name: Optional[str] = None
    password: Optional[str] = None
    comment: Optional[str] = None
    disabled: Optional[bool] = False


class MikrotikDeleteData(BaseModel):
    router: str
