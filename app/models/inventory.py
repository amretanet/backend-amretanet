from enum import Enum
from typing import Optional
from pydantic import BaseModel

# responses
InventoryProjections = {
    "name": 1,
    "id_category": 1,
    "category": {"$ifNull": ["$category.name", None]},
    "pic_name": {"$ifNull": ["$pic.name", None]},
    "pic_role": {"$ifNull": ["$pic.role", None]},
    "quantity": 1,
    "unit": 1,
    "description": 1,
    "last_entry": 1,
    "last_out": 1,
}
InventoryRequestProjections = {
    "name": {"$ifNull": ["$inventory.name", None]},
    "engineer": {"$ifNull": ["$engineer.name", None]},
    "quantity": 1,
    "status": 1,
    "created_at": 1,
    "id_engineer": 1,
    "id_inventory": 1,
}


# schemas
class InventoryInsertData(BaseModel):
    name: str
    id_category: str
    quantity: int
    unit: str
    description: Optional[str] = ""


class InventoryPositionData(str, Enum):
    WAREHOUSE = "WAREHOUSE"
    CUSTOMER = "CUSTOMER"
    ENGINEER = "ENGINEER"


class InventoryEngineerRequestStatusData(str, Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class InventoryEngineerRequestInsertData(BaseModel):
    id_engineer: str
    id_inventory: str
    quantity: int


class InventoryEngineerRequestUpdateStatusData(BaseModel):
    status: InventoryEngineerRequestStatusData
