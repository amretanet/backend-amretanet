from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.models.generals import Pagination
from app.models.odp import ODPInsertData
from app.models.users import UserData, UserRole
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetAggregateData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.models.odp import ODPProjections
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import GetCurrentDateTime, RemoveFilePath
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
)
from app.routes.v1.auth_routes import GetCurrentUser


router = APIRouter(prefix="/odp", tags=["Optical Distribution Point (ODP)"])


@router.get("")
async def get_odp(
    key: str = None,
    topology: str = None,
    is_maps_only: bool = False,
    page: int = 1,
    items: int = 1,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    query = {}
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
            {"location.address": {"$regex": key, "$options": "i"}},
        ]
    if topology:
        query["topology"] = topology

    pipeline = [
        {"$match": query},
        {"$sort": {"name": 1}},
        {
            "$lookup": {
                "from": "odc",
                "let": {"idParent": "$id_parent"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idParent"]}}},
                    {"$limit": 1},
                ],
                "as": "odc",
            }
        },
        {
            "$lookup": {
                "from": "odp",
                "let": {"idParent": "$id_parent"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idParent"]}}},
                    {"$limit": 1},
                ],
                "as": "odp",
            }
        },
        {
            "$addFields": {
                "parent_name": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$odc.name", 0]},
                        {"$arrayElemAt": ["$odp.name", 0]},
                    ]
                }
            }
        },
    ]

    odp_maps_data = await GetAggregateData(db.odp, pipeline, ODPProjections)
    if is_maps_only:
        return JSONResponse(content={"odp_maps_data": odp_maps_data})

    odp_data, count = await GetManyData(
        db.odp, pipeline, ODPProjections, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}

    return JSONResponse(
        content={
            "odp_data": odp_data,
            "odp_maps_data": odp_maps_data,
            "pagination_info": pagination_info,
        }
    )


@router.post("/add")
async def create_odp(
    data: ODPInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.odp, {"name": payload["name"]})
    if exist_data:
        raise HTTPException(
            status_code=400, detail={"message": "Nama ODP Telah Digunakan!"}
        )

    payload["id_parent"] = ObjectId(payload["id_parent"])
    payload["created_at"] = GetCurrentDateTime()
    result = await CreateOneData(db.odp, payload)
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_odp(
    id: str,
    data: ODPInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.odp, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    exist_name = await GetOneData(
        db.odp, {"name": payload["name"], "_id": {"$ne": ObjectId(id)}}
    )
    if exist_name:
        raise HTTPException(
            status_code=400, detail={"message": "Nama ODP Telah Digunakan!"}
        )

    payload["id_parent"] = ObjectId(payload["id_parent"])
    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(db.odp, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    if payload.get("image_url", "") != exist_data.get("exist_data", ""):
        RemoveFilePath(exist_data.get("image_url", ""))

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_odp(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    exist_data = await GetOneData(db.odp, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.odp, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    RemoveFilePath(exist_data.get("image_url", ""))
    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
