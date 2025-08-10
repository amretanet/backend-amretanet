from fastapi import APIRouter, Depends, Body, HTTPException
from fastapi.responses import JSONResponse
from bson import ObjectId
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    EXIST_DATA_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from app.modules.generals import GetCurrentDateTime
from app.models.users import UserData
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.models.categories import CategoryInsertData, CategoryTypeData
from app.routes.v1.auth_routes import GetCurrentUser
from dotenv import load_dotenv

load_dotenv()


router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("")
async def get_inventory_categories(
    key: str = None,
    page: int = 1,
    items: int = 10,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    pipeline = []
    query = {
        "type": CategoryTypeData.INVENTORY.value,
    }
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
        ]

    pipeline.append({"$match": query})
    pipeline.append({"$sort": {"created_at": -1}})

    category_data, count = await GetManyData(
        db.categories, pipeline, {}, {"page": 1, "items": items}
    )
    return JSONResponse(
        content={
            "category_data": category_data,
            "pagination_info": {"page": page, "items": items, "count": count},
        }
    )


@router.post("/add")
async def create_inventory_category(
    data: CategoryInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(
        db.categories,
        {
            "type": payload["type"],
            "$or": [
                {"name": payload["name"]},
                {"name": payload["name"].strip()},
                {"name": payload["name"].lower()},
                {"name": payload["name"].upper()},
                {"name": payload["name"].title()},
            ],
        },
    )
    if exist_data:
        raise HTTPException(status_code=400, detail={"message": EXIST_DATA_MESSAGE})

    payload["created_at"] = GetCurrentDateTime()

    result = await CreateOneData(db.categories, payload)
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_inventory_category(
    id: str,
    data: CategoryInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.categories, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    exist_name = await GetOneData(
        db.categories,
        {
            "_id": {"$ne": ObjectId(id)},
            "type": payload["type"],
            "$or": [
                {"name": payload["name"]},
                {"name": payload["name"].strip()},
                {"name": payload["name"].lower()},
                {"name": payload["name"].upper()},
                {"name": payload["name"].title()},
            ],
        },
    )
    if exist_name:
        raise HTTPException(status_code=400, detail={"message": EXIST_DATA_MESSAGE})

    payload["updated_at"] = GetCurrentDateTime()

    result = await UpdateOneData(
        db.categories, {"_id": ObjectId(id)}, {"$set": payload}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_inventory_category(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.categories, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.categories, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
