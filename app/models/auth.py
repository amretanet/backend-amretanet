from typing import Optional
from pydantic import BaseModel
from app.models.users import UserData


# schemas
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_data: UserData
    customer_data: Optional[dict] = None


class TokenData(BaseModel):
    id: str
    username: Optional[str] = None
    role: Optional[int] = 0


class RefreshTokenPayload(BaseModel):
    refresh_token: str
    uid: str
