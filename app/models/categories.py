from enum import Enum
from pydantic import BaseModel


class CategoryTypeData(str, Enum):
    INVENTORY = "INVENTORY"


class CategoryInsertData(BaseModel):
    name: str
    type: CategoryTypeData = CategoryTypeData.INVENTORY.value
    description: str = None
