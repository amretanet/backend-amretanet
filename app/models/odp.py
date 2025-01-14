from typing import Optional
from pydantic import BaseModel
from app.models.generals import Location
from enum import Enum

# responses
ODPProjections = {
    "id_parent": 1,
    "name": 1,
    "topology": 1,
    "image_url": 1,
    "location": 1,
    "port": 1,
    "capacity": 1,
    "available": 1,
    "damping": 1,
    "tube": 1,
    "description": 1,
    "parent_name": 1,
}


# schemas
class TopologyData(str, Enum):
    STAR = "STAR"
    TREE = "TREE"


class ODPInsertData(BaseModel):
    id_parent: str
    name: str
    topology: TopologyData
    image_url: str
    location: Location
    port: int
    capacity: int
    available: int
    damping: str
    tube: str
    description: Optional[str] = None
