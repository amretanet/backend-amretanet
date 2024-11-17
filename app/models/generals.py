from enum import Enum
from pydantic import BaseModel


# schemas
class Pagination(BaseModel):
    page: int = 1
    item: int = 10
    count: int


class Source(int, Enum):
    instagram = 1
    twitter = 2
    youtube = 3
    tiktok = 4


class Gender(str, Enum):
    male = "L"
    female = "P"
