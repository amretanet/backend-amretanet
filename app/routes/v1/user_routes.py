from bson import ObjectId
from fastapi import APIRouter, Depends, Body, HTTPException
from fastapi.responses import JSONResponse
from app.modules.crud_operations import (
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
    CreateOneData,
)
from app.models.generals import Pagination
from app.models.users import (
    UserChangePasswordData,
    UserData,
    UserInsertData,
    UserRole,
    UserUpdateData,
)
from app.models.users import UserProjections
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import (
    GenerateReferralCode,
    GetCurrentDateTime,
    ObjectIDValidator,
)
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
    OBJECT_ID_NOT_VALID_MESSAGE,
)
from app.routes.v1.auth_routes import (
    GetCurrentUser,
    VerifyPassword,
)
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CUSTOMER_PASSWORD = os.getenv("DEFAULT_CUSTOMER_PASSWORD")
DEFAULT_MANAGEMENT_PASSWORD = os.getenv("DEFAULT_MANAGEMENT_PASSWORD")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/user", tags=["Users"])


@router.get("")
async def get_users(
    key: str = None,
    role: UserRole = None,
    page: int = 1,
    items: int = 10,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )

    query = {}
    if key:
        query = {
            "$or": [
                {"name": {"$regex": key, "$options": "i"}},
                {"email": {"$regex": key, "$options": "i"}},
                {"phone_number": {"$regex": key, "$options": "i"}},
                {"referral": {"$regex": key, "$options": "i"}},
            ]
        }
    if role:
        query["role"] = role

    pipeline = [
        {"$match": query},
        {"$sort": {"role": 1, "name": 1}},
    ]

    user_data, count = await GetManyData(
        db.users, pipeline, UserProjections, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}

    return JSONResponse(
        content={"user_data": user_data, "pagination_info": pagination_info}
    )


@router.get("/detail/{id}")
async def get_user_detail(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    id_user = ObjectIDValidator(id)
    if not id_user:
        raise HTTPException(
            status_code=400, detail={"message": OBJECT_ID_NOT_VALID_MESSAGE}
        )

    user_data = await GetOneData(db.users, {"_id": id_user}, UserProjections)
    if not user_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    return JSONResponse(
        content={"user_data": user_data},
    )


@router.post("/add")
async def create_user(
    data: UserInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )

    payload = data.dict(exclude_unset=True)
    exist_user_data = await GetOneData(db.users, {"email": payload["email"]})
    if exist_user_data:
        raise HTTPException(
            status_code=400, detail={"message": "Email Telah Tersedia!"}
        )

    payload["referral"] = GenerateReferralCode(payload["email"])
    payload["created_at"] = GetCurrentDateTime()
    payload["password"] = pwd_context.hash(payload["password"])
    result = await CreateOneData(db.users, payload)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_user(
    id: str,
    data: UserUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_user_data = await GetOneData(db.users, {"_id": ObjectId(id)})
    if not exist_user_data:
        raise HTTPException(status_code=400, detail={"message": NOT_FOUND_MESSAGE})

    payload = data.dict(exclude_unset=True)
    exist_email_data = await GetOneData(
        db.users, {"email": payload["email"], "_id": {"$ne": ObjectId(id)}}
    )
    if exist_email_data:
        raise HTTPException(
            status_code=400, detail={"message": "Email Telah Tersedia!"}
        )

    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(db.users, {"_id": ObjectId(id)}, {"$set": payload})
    if not result.modified_count:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    await UpdateOneData(
        db.customers,
        {"id_user": ObjectId(id)},
        {
            "$set": {
                "name": payload["name"],
                "email": payload["email"],
                "phone_number": payload["phone_number"],
                "gender": payload["gender"],
                "location.address": payload["address"],
            }
        },
    )
    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_user(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    exist_user = await GetOneData(db.users, {"_id": ObjectId(id)})
    if not exist_user:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.users, {"_id": ObjectId(id)})
    if not result.deleted_count:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    await DeleteOneData(db.customers, {"id_user": ObjectId(id)})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})


@router.put("/reset-password/{id}")
async def reset_password(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    exist_user = await GetOneData(db.users, {"_id": ObjectId(id)})
    if not exist_user:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    if exist_user["role"] == UserRole.CUSTOMER.value:
        password = pwd_context.hash(DEFAULT_CUSTOMER_PASSWORD)
    else:
        password = pwd_context.hash(DEFAULT_MANAGEMENT_PASSWORD)

    result = await UpdateOneData(
        db.users, {"_id": ObjectId(id)}, {"$set": {"password": password}}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": "Password Telah Direset!"})


@router.put("/change-password/{id}")
async def change_password(
    id: str,
    data: UserChangePasswordData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    new_password = payload["new_password"]
    confirm_new_password = payload["confirm_new_password"]
    if not new_password == confirm_new_password:
        raise HTTPException(
            status_code=400, detail={"message": "Konfirmasi Password Tidak Sesuai!"}
        )

    projections = {"_id": {"$toString": "$_id"}, "password": 1}
    user_data = await GetOneData(db.users, {"_id": ObjectId(id)}, projections)
    if not user_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    is_password_verified = await VerifyPassword(
        payload["old_password"], user_data["password"]
    )
    if not is_password_verified:
        raise HTTPException(
            status_code=400, detail={"message": "Password Lama Tidak Sesuai!"}
        )

    update_data = {}
    update_data["password"] = pwd_context.hash(new_password)
    update_data["updated_password_at"] = GetCurrentDateTime()
    result = await UpdateOneData(db.users, {"_id": ObjectId(id)}, {"$set": update_data})
    if not result.modified_count:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})

@router.get("/list-collectors")
async def list_collectors(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    collector_roles = [ UserRole.ENGINEER, UserRole.BILL_COLLECTOR]
    role_values = [role.value for role in collector_roles]

    cursor = db.users.find(
        { "role": { "$in": role_values } },
        { "name": 1, "email": 1, "role": 1, "status": 1, "_id": 0 } 
    )
    users = await cursor.to_list(length=100)

    return JSONResponse(content={"users": users})