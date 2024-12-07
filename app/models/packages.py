from typing import Optional
from pydantic import BaseModel
from enum import Enum


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
