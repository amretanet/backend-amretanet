from bson import ObjectId
from fastapi import APIRouter, Depends, Body
from fastapi.responses import JSONResponse
from app.modules.crud_operations import (
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
    CreateOneData,
)
from app.modules.cryptography import RSADecryption
from app.models.generals import Pagination
from app.models.users import (
    UserChangePasswordData,
    UserData,
    UserInsertData,
    UserRole,
    UserUpdateData,
)
from app.models.users import UserProjections
from app.modules.database import AsyncIOMotorClient, GetBMDatabase
from app.modules.generals import (
    GetCurrentDateTime,
    ObjectIDValidator,
    ResponseFormatter,
)
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    DEFAULT_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    NOT_AVAILABLE_MESSAGE,
    NOT_FOUND_MESSAGE,
    OBJECT_ID_NOT_VALID_MESSAGE,
)
from app.routes.v1.auth_routes import (
    GetCurrentUser,
    VerifyPassword,
)
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/user", tags=["Users"])


@router.get("")
async def get_users(
    key: str = None,
    page: int = 1,
    item: int = 10,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetBMDatabase),
):
    query = {}
    if key is not None:
        query = {
            "$or": [
                {"name": {"$regex": key, "$options": "i"}},
                {"username": {"$regex": key, "$options": "i"}},
            ]
        }
    query["id_project"] = current_user.id_project
    pipeline = [{"$match": query}, {"$sort": {"name": 1}}]

    user_data, count = await GetManyData(
        db.users, pipeline, UserProjections, {"page": page, "item": item}
    )
    pagination: Pagination = {"page": page, "item": item, "count": count}
    if len(user_data) == 0:
        response = ResponseFormatter({}, NOT_AVAILABLE_MESSAGE)
        return JSONResponse(status_code=404, content=response)

    response = ResponseFormatter(
        {"user_data": user_data, "pagination_info": pagination}, "", True
    )
    return JSONResponse(status_code=200, content=response)


@router.get("/detail/{id}")
async def get_user_detail(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetBMDatabase),
):
    id_user = ObjectIDValidator(id)
    if not id_user:
        response = ResponseFormatter({}, OBJECT_ID_NOT_VALID_MESSAGE)
        return JSONResponse(status_code=400, content=response)

    user_data = await GetOneData(db.users, {"_id": id_user}, UserProjections)
    if not user_data:
        response = ResponseFormatter({}, NOT_FOUND_MESSAGE)
        return JSONResponse(status_code=404, content=response)

    response = ResponseFormatter({"user_data": user_data}, "", True)
    return JSONResponse(status_code=200, content=response)


@router.post("/add")
async def create_user(
    data: UserInsertData = Body(..., embed=True),
    # current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetBMDatabase),
):
    # if not current_user.role == UserRole.admin:
    #     response = ResponseFormatter({}, FORBIDDEN_ACCESS_MESSAGE)
    #     return JSONResponse(status_code=403, content=response)

    payload = data.dict()
    exist_user_data = await GetOneData(db.users, {"username": payload["username"]})
    if exist_user_data:
        response = ResponseFormatter({}, "Username Telah Tersedia!")
        return JSONResponse(status_code=400, content=response)

    payload["created_at"] = GetCurrentDateTime()
    payload["password"] = await RSADecryption(payload["password"])
    payload["password"] = pwd_context.hash(payload["password"])
    result = await CreateOneData(db.users, payload)
    if not result.inserted_id:
        print("Gagal")
        response = ResponseFormatter({}, DEFAULT_MESSAGE)
        return JSONResponse(status_code=500, content=response)

    response = ResponseFormatter({}, DATA_HAS_INSERTED_MESSAGE, True)
    return JSONResponse(status_code=200, content=response)


@router.put("/update/{id}")
async def update_user(
    id: str,
    data: UserUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetBMDatabase),
):
    if not current_user.role == UserRole.admin:
        response = ResponseFormatter({}, FORBIDDEN_ACCESS_MESSAGE)
        return JSONResponse(status_code=403, content=response)

    exist_user_data = await GetOneData(db.users, {"_id": ObjectId(id)})
    if not exist_user_data:
        response = ResponseFormatter({}, NOT_FOUND_MESSAGE)
        return JSONResponse(status_code=400, content=response)

    payload = data.dict()
    exist_username_data = await GetOneData(
        db.users, {"username": payload["username"], "_id": {"$ne": ObjectId(id)}}
    )
    if exist_username_data:
        response = ResponseFormatter({}, "Username Telah Tersedia!")
        return JSONResponse(status_code=403, content=response)

    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(db.users, {"_id": ObjectId(id)}, {"$set": payload})
    if not result.modified_count:
        response = ResponseFormatter({}, DEFAULT_MESSAGE)
        return JSONResponse(status_code=500, content=response)

    response = ResponseFormatter({}, DATA_HAS_UPDATED_MESSAGE, True)
    return JSONResponse(status_code=200, content=response)


@router.delete("/delete/{id}")
async def delete_user(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetBMDatabase),
):
    if not current_user.role == UserRole.admin:
        response = ResponseFormatter({}, FORBIDDEN_ACCESS_MESSAGE)
        return JSONResponse(status_code=403, content=response)

    exist_user = await GetOneData(db.users, {"_id": ObjectId(id)})
    if not exist_user:
        response = ResponseFormatter({}, NOT_FOUND_MESSAGE)
        return JSONResponse(status_code=404, content=response)

    result = await DeleteOneData(db.users, {"_id": ObjectId(id)})
    if not result.deleted_count:
        response = ResponseFormatter({}, DEFAULT_MESSAGE)
        return JSONResponse(status_code=500, content=response)

    response = ResponseFormatter({}, DATA_HAS_DELETED_MESSAGE, True)
    return JSONResponse(status_code=200, content=response)


@router.put("/change-password/{id}")
async def change_password(
    id: str,
    data: UserChangePasswordData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetBMDatabase),
):
    payload = data.dict()
    new_password = await RSADecryption(payload["new_password"])
    confirm_new_password = await RSADecryption(payload["confirm_new_password"])
    if not new_password == confirm_new_password:
        response = ResponseFormatter({}, "Konfirmasi Password Tidak Sesuai!")
        return JSONResponse(status_code=400, content=response)

    projections = {"_id": {"$toString": "$_id"}, "password": 1}
    user_data = await GetOneData(db.users, {"_id": ObjectId(id)}, projections)
    if not user_data:
        response = ResponseFormatter({}, NOT_FOUND_MESSAGE)
        return JSONResponse(status_code=404, content=response)

    is_password_verified = await VerifyPassword(
        payload["old_password"], user_data["password"]
    )
    if not is_password_verified:
        response = ResponseFormatter({}, "Password Lama Tidak Sesuai!")
        return JSONResponse(status_code=400, content=response)

    update_data = {}
    update_data["password"] = pwd_context.hash(new_password)
    update_data["updated_password_at"] = GetCurrentDateTime()
    result = await UpdateOneData(db.users, {"_id": ObjectId(id)}, {"$set": update_data})
    if not result.modified_count:
        response = ResponseFormatter({}, DEFAULT_MESSAGE)
        return JSONResponse(status_code=500, content=response)

    response = ResponseFormatter({}, DATA_HAS_UPDATED_MESSAGE, True)
    return JSONResponse(status_code=200, content=response)
