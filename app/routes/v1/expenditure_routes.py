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
    FORBIDDEN_ACCESS_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from fastapi.responses import JSONResponse
from app.models.expenditures import ExpenditureInsertData, ExpenditureUpdateData
from app.models.users import UserData, UserRole
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

router = APIRouter(prefix="/expenditure", tags=["Exependitures"])


@router.get("")
async def get_expenditures(
    key: str = None,
    from_date: datetime = None,
    to_date: datetime = None,
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
            {"category": {"$regex": key, "$options": "i"}},
            {"method": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
        ]

    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}

    pipeline = [
        {"$match": query},
        {"$sort": {"date": -1}},
        {
            "$lookup": {
                "from": "users",
                "let": {"idReceiver": "$id_receiver"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idReceiver"]}}},
                    {"$project": {"name": 1, "email": 1, "phone_number": 1}},
                ],
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

    expenditure_data, count = await GetManyData(
        db.expenditures, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "expenditure_data": expenditure_data,
            "pagination_info": pagination_info,
        }
    )


@router.get("/stats")
async def get_expenditure_stats(
    key: str = None,
    from_date: datetime = None,
    to_date: datetime = None,
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
            {"category": {"$regex": key, "$options": "i"}},
            {"method": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
        ]
    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}

    pipeline = [
        {"$match": query},
        {"$group": {"_id": None, "count": {"$sum": "$nominal"}}},
        {"$project": {"_id": 0, "count": 1}},
    ]

    expenditure_count, _ = await GetManyData(db.expenditures, pipeline, {})
    return JSONResponse(
        content={
            "expenditure_count": expenditure_count[0]["count"]
            if len(expenditure_count) > 0
            else 0
        }
    )


@router.post("/add")
async def create_expenditure(
    data: ExpenditureInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    payload["category"] = str(payload["category"]).upper()
    payload["created_at"] = GetCurrentDateTime()
    payload["created_by"] = ObjectId(current_user.id)
    result = await CreateOneData(db.expenditures, payload)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_expenditure(
    id: str,
    data: ExpenditureUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.expenditures, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    if "category" in payload:
        payload["category"] = str(payload["category"]).upper()
    payload["updated_at"] = GetCurrentDateTime()
    payload["updated_by"] = ObjectId(current_user.id)
    result = await UpdateOneData(
        db.expenditures, {"_id": ObjectId(id)}, {"$set": payload}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_expenditure(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    exist_data = await GetOneData(db.expenditures, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.expenditures, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
