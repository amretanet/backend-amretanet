from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.models.generals import Pagination
from app.models.coverage_areas import CoverageAreaInsertData
from app.models.users import UserData, UserRole
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetAggregateData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.models.coverage_areas import CoverageAreaProjections
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import GetCurrentDateTime
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
    EXIST_DATA_MESSAGE,
)
from app.routes.v1.auth_routes import GetCurrentUser


router = APIRouter(prefix="/coverage-area", tags=["Coverage Area"])


@router.get("")
async def get_coverage_areas(
    key: str = None,
    is_maps_only: bool = False,
    page: int = 1,
    items: int = 1,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
            {"address.location_name": {"$regex": key, "$options": "i"}},
        ]

    pipeline = [{"$match": query}, {"$sort": {"name": 1}}]

    coverage_area_maps_data = await GetAggregateData(
        db.coverage_areas, pipeline, CoverageAreaProjections
    )
    if is_maps_only:
        return JSONResponse(
            content={"coverage_area_maps_data": coverage_area_maps_data}
        )

    coverage_area_data, count = await GetManyData(
        db.coverage_areas,
        pipeline,
        CoverageAreaProjections,
        {"page": page, "items": items},
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "coverage_area_data": coverage_area_data,
            "coverage_area_maps_data": coverage_area_maps_data,
            "pagination_info": pagination_info,
        }
    )


@router.post("/add")
async def create_coverage_area(
    data: CoverageAreaInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    payload["name"] = payload["name"].strip()
    exist_data = await GetOneData(db.coverage_areas, {"name": payload["name"]})
    if exist_data:
        raise HTTPException(status_code=400, detail={"message": EXIST_DATA_MESSAGE})

    payload["address"]["rt"] = str(payload["address"]["rt"]).zfill(3)
    payload["address"]["rw"] = str(payload["address"]["rw"]).zfill(3)
    payload["created_at"] = GetCurrentDateTime()
    result = await CreateOneData(db.coverage_areas, payload)
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_coverage_area(
    id: str,
    data: CoverageAreaInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    payload["name"] = payload["name"].strip()
    exist_data = await GetOneData(db.coverage_areas, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    exist_name = await GetOneData(
        db.coverage_areas, {"name": payload["name"], "_id": {"$ne": ObjectId(id)}}
    )
    if exist_name:
        raise HTTPException(status_code=400, detail={"message": EXIST_DATA_MESSAGE})

    payload["address"]["rt"] = str(payload["address"]["rt"]).zfill(3)
    payload["address"]["rw"] = str(payload["address"]["rw"]).zfill(3)
    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(
        db.coverage_areas, {"_id": ObjectId(id)}, {"$set": payload}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_coverage_area(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    exist_data = await GetOneData(db.coverage_areas, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.coverage_areas, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
