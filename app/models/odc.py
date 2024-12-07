from typing import Optional
from pydantic import BaseModel
from app.models.generals import Location


# schemas
class ODCInsertData(BaseModel):
    name: str
    image_url: Optional[str] = None
    location: Location
    port: int
    capacity: int
    available: int
    damping: str
    tube: str
    description: Optional[str] = None
