from typing import Optional
from pydantic import BaseModel
from app.models.users import UserData

# schemas


class LoginData(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user_data: UserData


class TokenData(BaseModel):
    id: str
    username: Optional[str] = None
    role: Optional[int] = 0


class RefreshTokenPayload(BaseModel):
    refresh_token: str
    uid: str
