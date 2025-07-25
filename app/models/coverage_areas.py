from pydantic import BaseModel

# responses
CoverageAreaProjections = {
    "name": 1,
    "address": 1,
    "capacity": 1,
    "available": 1,
}


# schemas
class CoverageAddressData(BaseModel):
    province: str = "Jawa Barat"
    regency: str
    subdistrict: str
    village: str
    rw: str
    rt: str
    location_name: str
    postal_code: int
    latitude: float
    longitude: float


class CoverageAreaInsertData(BaseModel):
    name: str
    address: CoverageAddressData
    capacity: int = 0
    available: int = 0
