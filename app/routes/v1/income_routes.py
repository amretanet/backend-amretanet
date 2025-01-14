from datetime import datetime, timedelta
from bson import SON, ObjectId
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
from app.models.incomes import IncomeInsertData, IncomeUpdateData
from app.models.users import UserData, UserRole
from app.models.generals import Pagination
from app.modules.generals import GetCurrentDateTime
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetAggregateData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase


def GetIncomeStatsDatesFilter():
    now = GetCurrentDateTime()

    # today
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_today = now.replace(hour=23, minute=59, second=59, microsecond=0)

    # this week
    start_of_week = start_today - timedelta(days=6)
    end_of_week = end_today

    # this month
    start_of_month = start_today.replace(day=1)
    end_of_month = end_today

    # last month
    start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
    end_of_last_month = (start_of_month - timedelta(days=1)).replace(
        hour=23, minute=59, second=59, microsecond=0
    )

    # current year
    start_of_year = now.replace(
        month=1, day=1, hour=0, minute=0, second=0, microsecond=0
    )
    end_of_year = now.replace(
        month=12, day=31, hour=23, minute=59, second=59, microsecond=0
    )

    return {
        "today": (start_today, end_today),
        "this_week": (start_of_week, end_of_week),
        "this_month": (start_of_month, end_of_month),
        "last_month": (start_of_last_month, end_of_last_month),
        "this_year": (start_of_year, end_of_year),
    }


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
    if receiver:
        query["id_receiver"] = ObjectId(receiver)

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


@router.get("/count")
async def get_income_count(
    key: str = None,
    receiver: str = None,
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
    if receiver:
        query["id_receiver"] = ObjectId(receiver)

    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}

    pipeline = [
        {"$match": query},
        {"$group": {"_id": None, "count": {"$sum": "$nominal"}}},
    ]

    income_count, _ = await GetManyData(db.incomes, pipeline, {"_id": 0, "count": 1})
    return JSONResponse(
        content={
            "income_count": income_count[0]["count"] if len(income_count) > 0 else 0
        }
    )


@router.get("/stats")
async def get_income_stats(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    dates = GetIncomeStatsDatesFilter()
    pipeline = [
        {
            "$facet": {
                "count": [
                    {"$group": {"_id": None, "total": {"$sum": "$nominal"}}},
                ],
                "today": [
                    {
                        "$match": {
                            "date": {
                                "$gte": dates["today"][0],
                                "$lt": dates["today"][1],
                            }
                        }
                    },
                    {"$group": {"_id": None, "total": {"$sum": "$nominal"}}},
                ],
                "current_week": [
                    {
                        "$match": {
                            "date": {
                                "$gte": dates["this_week"][0],
                                "$lt": dates["this_week"][1],
                            }
                        }
                    },
                    {"$group": {"_id": None, "total": {"$sum": "$nominal"}}},
                ],
                "current_month": [
                    {
                        "$match": {
                            "date": {
                                "$gte": dates["this_month"][0],
                                "$lt": dates["this_month"][1],
                            }
                        }
                    },
                    {"$group": {"_id": None, "total": {"$sum": "$nominal"}}},
                ],
                "last_month": [
                    {
                        "$match": {
                            "date": {
                                "$gte": dates["last_month"][0],
                                "$lt": dates["last_month"][1],
                            }
                        }
                    },
                    {"$group": {"_id": None, "total": {"$sum": "$nominal"}}},
                ],
                "current_year": [
                    {
                        "$match": {
                            "date": {
                                "$gte": dates["this_year"][0],
                                "$lt": dates["this_year"][1],
                            }
                        }
                    },
                    {"$group": {"_id": None, "total": {"$sum": "$nominal"}}},
                ],
            }
        },
    ]
    income_data = await GetAggregateData(
        db.incomes,
        pipeline,
        {
            "count": {"$arrayElemAt": ["$count.total", 0]},
            "today": {"$arrayElemAt": ["$today.total", 0]},
            "current_week": {"$arrayElemAt": ["$current_week.total", 0]},
            "current_month": {"$arrayElemAt": ["$current_month.total", 0]},
            "last_month": {"$arrayElemAt": ["$last_month.total", 0]},
            "current_year": {"$arrayElemAt": ["$current_year.total", 0]},
            "month_difference": {
                "$subtract": [
                    {"$arrayElemAt": ["$current_month.total", 0]},
                    {"$arrayElemAt": ["$last_month.total", 0]},
                ]
            },
            "month_difference_percentage": {
                "$cond": {
                    "if": {"$ne": [{"$arrayElemAt": ["$last_month.total", 0]}, 0]},
                    "then": {
                        "$multiply": [
                            {
                                "$divide": [
                                    {
                                        "$subtract": [
                                            {
                                                "$arrayElemAt": [
                                                    "$current_month.total",
                                                    0,
                                                ]
                                            },
                                            {
                                                "$arrayElemAt": [
                                                    "$last_month.total",
                                                    0,
                                                ]
                                            },
                                        ]
                                    },
                                    {"$arrayElemAt": ["$last_month.total", 0]},
                                ]
                            },
                            100,
                        ]
                    },
                    "else": 0,
                }
            },
            "month_trend": {
                "$cond": {
                    "if": {
                        "$gt": [
                            {"$arrayElemAt": ["$current_month.total", 0]},
                            {"$arrayElemAt": ["$last_month.total", 0]},
                        ]
                    },
                    "then": "increase",
                    "else": {
                        "$cond": {
                            "if": {
                                "$lt": [
                                    {"$arrayElemAt": ["$current_month.total", 0]},
                                    {"$arrayElemAt": ["$last_month.total", 0]},
                                ]
                            },
                            "then": "decrease",
                            "else": "no_change",
                        }
                    },
                }
            },
        },
    )
    income_stats = income_data[0] if len(income_data) > 0 else {}
    pipeline = [
        {
            "$match": {
                "status": {"$ne": "PAID"},
            },
        },
        {"$group": {"_id": None, "count": {"$sum": "$amount"}}},
    ]
    invoice_data = await GetAggregateData(db.invoices, pipeline)
    invoice_stats = invoice_data[0] if len(invoice_data) > 0 else {}
    income_stats["unpaid"] = invoice_stats.get("count", 0)

    return JSONResponse(
        content={
            "income_stats": income_stats,
        }
    )


@router.get("/cash-balance")
async def get_cash_balance(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    pipeline = [
        {"$addFields": {"month": {"$month": {"$toDate": "$date"}}}},
        {"$group": {"_id": "$month", "count": {"$sum": "$nominal"}}},
        {"$sort": SON([("_id", 1)])},
    ]
    income_data = await GetAggregateData(db.incomes, pipeline, {"count": 1})
    expenditure_data = await GetAggregateData(db.expenditures, pipeline, {"count": 1})

    categories = [
        "Januari",
        "Februari",
        "Maret",
        "April",
        "Mei",
        "Juni",
        "Juli",
        "Agustus",
        "September",
        "Oktober",
        "November",
        "Desember",
    ]
    incomes = []
    expenditures = []
    for index, item in enumerate(categories):
        income_result = next(
            (item for item in income_data if item["_id"] == index + 1), {}
        )
        incomes.append(income_result.get("count", 0))
        expenditure_result = next(
            (item for item in expenditure_data if item["_id"] == index + 1), {}
        )
        expenditures.append(expenditure_result.get("count", 0))

    income_count = sum(incomes)
    expenditure_count = sum(expenditures)
    cash_balance = income_count - expenditure_count
    return JSONResponse(
        content={
            "cash_balance": cash_balance,
            "categories": categories,
            "incomes": incomes,
            "expenditures": expenditures,
        }
    )


@router.post("/add")
async def create_income(
    data: IncomeInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
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
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
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
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    exist_data = await GetOneData(db.incomes, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.incomes, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
