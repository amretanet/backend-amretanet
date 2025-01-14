from typing import Optional
from pydantic import BaseModel
from app.models.generals import Location

# responses
ODCProjections = {
    "name": 1,
    "image_url": 1,
    "location": 1,
    "port": 1,
    "capacity": 1,
    "available": 1,
    "damping": 1,
    "tube": 1,
    "description": 1,
}


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
