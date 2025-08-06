from typing import Optional
from pydantic import BaseModel
from enum import Enum


class InventoryInsertData(BaseModel):
    name: str
    category: str
    quantity: int
    unit: str
    serial_number: str
