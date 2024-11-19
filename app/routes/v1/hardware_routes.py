from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.models.generals import Pagination, MapsProjections
from app.models.hardware import ODCInsertData, ODPInsertData
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
    EXIST_DATA_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
)
from app.routes.v1.auth_routes import GetCurrentUser


router = APIRouter(prefix="/hardware", tags=["Hardware"])


@router.get("/odc")
async def get_odc(
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
            {"description": {"$regex": key, "$options": "i"}},
            {"location.address": {"$regex": key, "$options": "i"}},
        ]

    pipeline = [{"$match": query}, {"$sort": {"name": 1}}]

    odc_data, count = await GetManyData(
        db.odc, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}

    odc_maps_data, _ = await GetManyData(db.odc, [], MapsProjections)
    return JSONResponse(
        content={
            "odc_data": odc_data,
            "odc_maps_data": odc_maps_data,
            "pagination_info": pagination_info,
        }
    )


@router.post("/odc/add")
async def create_odc(
    data: ODCInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = payload["name"].strip()
    exist_data = await GetOneData(db.odc, {"name": payload["name"]})
    if exist_data:
        raise HTTPException(status_code=400, detail={"message": EXIST_DATA_MESSAGE})

    payload["created_at"] = GetCurrentDateTime()
    result = await CreateOneData(db.odc, payload)
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/odc/update/{id}")
async def update_odc(
    id: str,
    data: ODCInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = payload["name"].strip()
    exist_data = await GetOneData(db.odc, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    exist_name = await GetOneData(
        db.odc, {"name": payload["name"], "_id": {"$ne": ObjectId(id)}}
    )
    if exist_name:
        raise HTTPException(
            status_code=400, detail={"message": "Nama ODC Telah Digunakan!"}
        )

    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(db.odc, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/odc/delete/{id}")
async def delete_odc(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.odc, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.odc, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    await DeleteManyData(db.odp, {"id_odc": ObjectId(id)})
    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})


@router.get("/odp")
async def get_odp(
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
            {"description": {"$regex": key, "$options": "i"}},
            {"location.address": {"$regex": key, "$options": "i"}},
        ]

    pipeline = [
        {"$match": query},
        {"$sort": {"name": 1}},
        {
            "$lookup": {
                "from": "odc",
                "localField": "id_odc",
                "foreignField": "_id",
                "as": "odc",
            }
        },
        {"$unwind": "$odc"},
        {"$addFields": {"odc": "$odc.name"}},
    ]

    odp_data, count = await GetManyData(
        db.odp, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}

    odp_maps_data, _ = await GetManyData(db.odp, [], MapsProjections)
    return JSONResponse(
        content={
            "odp_data": odp_data,
            "odp_maps_data": odp_maps_data,
            "pagination_info": pagination_info,
        }
    )


@router.post("/odp/add")
async def create_odp(
    data: ODPInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.odp, {"name": payload["name"]})
    if exist_data:
        raise HTTPException(status_code=400, detail={"message": EXIST_DATA_MESSAGE})

    payload["id_odc"] = ObjectId(payload["id_odc"])
    payload["created_at"] = GetCurrentDateTime()
    result = await CreateOneData(db.odp, payload)
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/odp/update/{id}")
async def update_odp(
    id: str,
    data: ODPInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
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

    payload["id_odc"] = ObjectId(payload["id_odc"])
    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(db.odp, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/odp/delete/{id}")
async def delete_odp(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.odp, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.odp, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
