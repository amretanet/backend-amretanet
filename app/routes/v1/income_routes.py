from datetime import datetime
from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
)
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from fastapi.responses import JSONResponse
from app.models.incomes import IncomeInsertData, IncomeUpdateData
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

router = APIRouter(prefix="/income", tags=["Incomes"])


@router.get("")
async def get_incomes(
    key: str = None,
    receiver: str = None,
    from_date: datetime = None,
    to_date: datetime = None,
    page: int = 1,
    items: int = 1,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if key:
        query["$or"] = [
            {"category": {"$regex": key, "$options": "i"}},
            {"method": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
        ]
    if receiver:
        query["id_receiver"] = ObjectId(receiver)

    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}

    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": -1}},
        {
            "$lookup": {
                "from": "users",
                "localField": "id_receiver",
                "foreignField": "_id",
                "pipeline": [{"$project": {"name": 1, "email": 1, "phone_number": 1}}],
                "as": "receiver",
            }
        },
        {
            "$addFields": {
                "receiver_name": {
                    "$ifNull": [{"$arrayElemAt": ["$receiver.name", 0]}, None]
                },
            }
        },
    ]

    income_data, count = await GetManyData(
        db.incomes, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "income_data": income_data,
            "pagination_info": pagination_info,
        }
    )


@router.get("/stats")
async def get_income_stats(
    key: str = None,
    receiver: str = None,
    from_date: datetime = None,
    to_date: datetime = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if key:
        query["$or"] = [
            {"category": {"$regex": key, "$options": "i"}},
            {"method": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
        ]
    if receiver:
        query["id_receiver"] = ObjectId(receiver)

    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}

    pipeline = [
        {"$match": query},
        {"$group": {"_id": None, "count": {"$sum": "$nominal"}}},
        {"$project": {"_id": 0, "count": 1}},
    ]

    income_count, _ = await GetManyData(db.incomes, pipeline, {})
    return JSONResponse(
        content={
            "income_count": income_count[0]["count"] if len(income_count) > 0 else 0
        }
    )


@router.post("/add")
async def create_income(
    data: IncomeInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    if "id_invoice" in payload and payload["id_invoice"]:
        payload["id_invoice"] = ObjectId(payload["id_invoice"])

    payload["category"] = str(payload["category"]).upper()
    payload["id_receiver"] = ObjectId(payload["id_receiver"])
    payload["created_at"] = GetCurrentDateTime()
    payload["created_by"] = ObjectId(current_user.id)
    result = await CreateOneData(db.incomes, payload)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_income(
    id: str,
    data: IncomeUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.incomes, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    if "id_invoice" in payload and payload["id_invoice"]:
        payload["id_invoice"] = ObjectId(payload["id_invoice"])
    if "id_receiver" in payload:
        payload["id_receiver"] = ObjectId(payload["id_receiver"])
    if "category" in payload:
        payload["category"] = str(payload["category"]).upper()
    payload["updated_at"] = GetCurrentDateTime()
    payload["updated_by"] = ObjectId(current_user.id)
    result = await UpdateOneData(db.incomes, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_income(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.incomes, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.incomes, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
