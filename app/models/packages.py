from typing import Optional
from pydantic import BaseModel
from enum import Enum

# responses
PackageProjections = {
    "name": 1,
    "router_profile": 1,
    "bandwidth": 1,
    "instalation_cost": 1,
    "maximum_device": 1,
    "price": 1,
    "is_displayed": 1,
    "category": 1,
    "description": 1,
}


# schemas
class PackageCategoryData(str, Enum):
    PPPOE = "PPPOE"
    ADD_ONS = "ADD-ONS"


class PackagePriceData(BaseModel):
    regular: int
    reseller: int


class PackageInsertData(BaseModel):
    name: str
    category: PackageCategoryData
    router_profile: Optional[str]
    bandwidth: Optional[int]
    instalation_cost: int
    maximum_device: int
    price: PackagePriceData
    is_displayed: int
    description: Optional[str] = None
