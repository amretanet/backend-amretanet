from typing import Optional
from pydantic import BaseModel
from app.models.generals import Location
from enum import Enum


# schemas
class TopologyData(str, Enum):
    star = "STAR"
    tree = "TREE"


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
