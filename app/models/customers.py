from typing import Optional
from pydantic import BaseModel

from app.models.generals import Gender


class IDCard(BaseModel):
    type: str
    number: str
    image_url: str


class Location(BaseModel):
    status: str
    address: str
    longitude: float
    latitude: float
    image_url: str


class Package(BaseModel):
    item: str
    mode: str
    router: str


class CustomerInsertData(BaseModel):
    name: str
    gender: Gender
    service_number: int
    id_card: IDCard
    location: Location
    email: str
    phone_number: str
    package: str
    due_date: int
    payment_type:str 
    ppn: Optional[int] = 0
    unique_code: Optional[str] = None
    odp_code:str
    odp_port:str
    router:str
    mode:str
    server:str
    
