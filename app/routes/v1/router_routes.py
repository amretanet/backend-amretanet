from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.models.generals import Pagination
from app.models.router import RouterInsertData
from app.models.users import UserData
from app.modules.crud_operations import (
    CreateOneData,
    DeleteManyData,
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import GetCurrentDateTime
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
)
from app.routes.v1.auth_routes import GetCurrentUser


router = APIRouter(prefix="/router", tags=["Routers"])


@router.get("")
async def get_router(
    key: str = None,
    page: int = 1,
    items: int = 1,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
            {"ip_address": {"$regex": key, "$options": "i"}},
            {"port": {"$regex": key, "$options": "i"}},
            {"username": {"$regex": key, "$options": "i"}},
        ]

    pipeline = [{"$match": query}, {"$sort": {"name": 1}}]

    router_data, count = await GetManyData(
        db.router, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "router_data": router_data,
            "pagination_info": pagination_info,
        }
    )


@router.post("/add")
async def create_router(
    data: RouterInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = payload["name"].strip()
    exist_data = await GetOneData(db.router, {"name": payload["name"]})
    if exist_data:
        raise HTTPException(
            status_code=400, detail={"message": "Nama Router Telah Digunakan!"}
        )

    payload["created_at"] = GetCurrentDateTime()
    result = await CreateOneData(db.router, payload)
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_router(
    id: str,
    data: RouterInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = payload["name"].strip()
    exist_data = await GetOneData(db.router, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    exist_name = await GetOneData(
        db.router, {"name": payload["name"], "_id": {"$ne": ObjectId(id)}}
    )
    if exist_name:
        raise HTTPException(
            status_code=400, detail={"message": "Nama Router Telah Digunakan!"}
        )

    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(db.router, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_router(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.router, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.router, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    await DeleteManyData(db.odp, {"id_router": ObjectId(id)})
    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
