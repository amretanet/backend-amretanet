from datetime import datetime, timedelta
from dateutil import tz
from typing import Optional
from fastapi.responses import JSONResponse
from app.modules.crud_operations import CreateOneData, GetOneData, UpdateOneData
from app.models.auth import RefreshTokenPayload, Token
from app.models.users import UserData
from app.modules.database import AsyncIOMotorClient, GetBMDatabase
from fastapi import Depends, HTTPException, status, APIRouter, Request, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt, ExpiredSignatureError
from passlib.context import CryptContext
from bson import ObjectId
import os
from dotenv import load_dotenv
from app.modules.cryptography import RSADecryption

load_dotenv()

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = os.environ["ALGORITHM"]
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"])
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.environ["REFRESH_TOKEN_EXPIRE_MINUTES"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


async def VerifyPassword(plain_password, hashed_password):
    try:
        password = await RSADecryption(plain_password)
        return pwd_context.verify(password, hashed_password)
    except Exception as e:
        print(e)
        return False


async def AuthenticateUser(username: str, password: str, db: AsyncIOMotorClient):
    user_data = await GetOneData(db.users, {"username": username})
    if not user_data:
        return False

    is_password_verified = await VerifyPassword(password, user_data["password"])
    if not is_password_verified:
        return False

    return user_data


def CreateAccessToken(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def GetCurrentUser(
    token: str = Depends(oauth2_scheme),
    db: AsyncIOMotorClient = Depends(GetBMDatabase),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id: str = payload.get("sub")
        username: int = payload.get("username")
        if id is None:
            raise credentials_exception
    except ExpiredSignatureError:
        credentials_exception.detail = "Token has expired"
        raise credentials_exception
    except JWTError:
        credentials_exception.detail = "Token is invalid"
        raise credentials_exception

    user = await GetOneData(db.users, {"username": username})

    if user is None:
        raise credentials_exception
    return UserData(**user)


router = APIRouter(
    tags=["Authentication"],
)


@router.post("/login", response_model=Token, response_model_by_alias=False)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorClient = Depends(GetBMDatabase),
):
    user = await AuthenticateUser(form_data.username, form_data.password, db)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau Password Salah!",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = {
        "sub": user["_id"],
        "role": user["role"],
        "username": user["username"],
    }

    refresh_token_payload = {"sub": user["_id"]}
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = CreateAccessToken(data=payload, expires_delta=access_token_expires)
    refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    refresh_token = CreateAccessToken(
        data=refresh_token_payload, expires_delta=refresh_token_expires
    )

    to_zone = tz.gettz("Asia/Jakarta")
    today = datetime.now()
    access_log_payload = {
        "user_id": user["_id"],
        "username": user["username"],
        "ip": request.client.host,
        "user_agent": request.headers.get("User-Agent"),
        "refresh_token": refresh_token,
        "date": today.astimezone(to_zone),
        "valid": True,
    }
    await db.access_logs.insert_one(access_log_payload)
    del user["password"]

    response: Token = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "user_data": user,
    }

    return response


@router.get("/verify")
async def verify_token(current_user: UserData = Depends(GetCurrentUser)):
    return JSONResponse(
        status_code=200, content={"status": "Ok!", "uid": current_user.id}
    )


@router.post("/refresh-token")
async def refresh_token(
    request: Request,
    data: RefreshTokenPayload = Body(..., embed=True),
    db: AsyncIOMotorClient = Depends(GetBMDatabase),
):
    try:
        payload = jwt.decode(data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        id: str = payload.get("sub")
        exp: str = payload.get("exp")

        if id is None or id != data.uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Refresh Token Tidak Valid!"},
            )

        check_refresh_token = await GetOneData(
            db.access_logs, {"refresh_token": data.refresh_token, "valid": True}
        )
        if check_refresh_token:
            user = await GetOneData(db.users, {"_id": ObjectId(id)})
            payload = {
                "sub": user["_id"],
                "role": user["role"],
                "username": user["username"],
            }
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = CreateAccessToken(
                data=payload, expires_delta=access_token_expires
            )
            refresh_token = data.refresh_token

            time_remaining = (exp - int(datetime.now().timestamp())) / 60
            if time_remaining < 15:
                refresh_token_payload = {"sub": id}
                refresh_token_expires = timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
                refresh_token = CreateAccessToken(
                    data=refresh_token_payload, expires_delta=refresh_token_expires
                )

                to_zone = tz.gettz("Asia/Jakarta")
                today = datetime.now()
                access_log_payload = {
                    "user_id": user.id,
                    "username": user.username,
                    "ip": request.client.host,
                    "user_agent": request.headers.get("User-Agent"),
                    "refresh_token": refresh_token,
                    "date": today.astimezone(to_zone),
                    "valid": True,
                }
                await CreateOneData(db.access_logs, access_log_payload)
                await UpdateOneData(
                    db.access_logs,
                    {"refresh_token": data.refresh_token},
                    {"$set": {"valid": False}},
                )

            return JSONResponse(
                status_code=200,
                content={
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "Bearer",
                },
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "Refresh Token Tidak Valid!"},
            )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Refresh Token Telah Habis!"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Refresh Token Tidak Valid!"},
        )
