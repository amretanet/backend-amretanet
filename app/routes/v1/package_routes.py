from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
)
from app.models.packages import PackageCategoryData, PackageInsertData
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from fastapi.responses import JSONResponse
from app.models.users import UserData
from app.models.generals import Pagination
from app.modules.generals import GetCurrentDateTime
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase

router = APIRouter(prefix="/package", tags=["Packages"])


@router.get("")
async def get_packages(
    key: str = None,
    category: PackageCategoryData = None,
    is_displayed: int = None,
    page: int = 1,
    items: int = 10,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
            {"location.address": {"$regex": key, "$options": "i"}},
        ]
    if category:
        query["category"] = category

    if is_displayed is not None:
        query["is_displayed"] = is_displayed

    pipeline = [{"$match": query}, {"$sort": {"name": 1}}]

    package_data, count = await GetManyData(
        db.packages, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "package_data": package_data,
            "pagination_info": pagination_info,
        }
    )


@router.post("/add")
async def create_package(
    data: PackageInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = payload["name"].strip()
    exist_data = await GetOneData(db.packages, {"name": payload["name"]})
    if exist_data:
        raise HTTPException(
            status_code=400, detail={"message": "Nama Paket Telah Digunakan!"}
        )

    if payload["category"] == PackageCategoryData.ADD_ONS:
        payload["router_profile"] = None
        payload["bandwidth"] = None

    payload["created_at"] = GetCurrentDateTime()
    result = await CreateOneData(db.packages, payload)
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_package(
    id: str,
    data: PackageInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = payload["name"].strip()
    exist_data = await GetOneData(db.packages, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    exist_name = await GetOneData(
        db.packages, {"name": payload["name"], "_id": {"$ne": ObjectId(id)}}
    )
    if exist_name:
        raise HTTPException(
            status_code=400, detail={"message": "Nama package Telah Digunakan!"}
        )

    if payload["category"] == PackageCategoryData.ADD_ONS:
        payload["router_profile"] = None
        payload["bandwidth"] = None
    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(db.packages, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_package(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.packages, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.packages, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
