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
from app.modules.whatsapp_message import SendWhatsappTicketOpenMessage
from app.modules.telegram_message import SendTelegramTicketOpenMessage
from app.models.notifications import NotificationTypeData
from app.models.tickets import TicketInsertData, TicketStatusData, TicketUpdateData
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

router = APIRouter(prefix="/ticket", tags=["Tickets"])


@router.get("")
async def get_tickets(
    key: str = None,
    status: TicketStatusData = None,
    page: int = 1,
    items: int = 1,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
            {"title": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
        ]
    if status:
        query["status"] = status
    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": -1}},
        {
            "$lookup": {
                "from": "users",
                "localField": "id_reporter",
                "foreignField": "_id",
                "as": "reporter",
                "pipeline": [{"$project": {"name": 1}}],
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "id_assignee",
                "foreignField": "_id",
                "as": "assignee",
                "pipeline": [{"$project": {"name": 1}}],
            }
        },
        {
            "$lookup": {
                "from": "odc",
                "localField": "id_odc",
                "foreignField": "_id",
                "as": "odc",
                "pipeline": [{"$project": {"name": 1}}],
            }
        },
        {
            "$lookup": {
                "from": "odp",
                "localField": "id_odp",
                "foreignField": "_id",
                "as": "odp",
                "pipeline": [{"$project": {"name": 1}}],
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "id_assignee",
                "foreignField": "_id",
                "as": "assignee",
                "pipeline": [{"$project": {"name": 1}}],
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "created_by",
                "foreignField": "_id",
                "as": "creator",
                "pipeline": [{"$project": {"name": 1}}],
            }
        },
        {
            "$lookup": {
                "from": "customers",
                "localField": "id_reporter",
                "foreignField": "id_user",
                "as": "customer",
            }
        },
        {"$unwind": {"path": "$customer", "preserveNullAndEmptyArrays": True}},
        {
            "$addFields": {
                "reporter": {
                    "$ifNull": [{"$arrayElemAt": ["$reporter.name", 0]}, None]
                },
                "assignee": {
                    "$ifNull": [{"$arrayElemAt": ["$assignee.name", 0]}, None]
                },
                "creator": {"$ifNull": [{"$arrayElemAt": ["$creator.name", 0]}, None]},
                "odc": {"$ifNull": [{"$arrayElemAt": ["$odc.name", 0]}, None]},
                "odp": {"$ifNull": [{"$arrayElemAt": ["$odp.name", 0]}, None]},
            }
        },
    ]

    ticket_data, count = await GetManyData(
        db.tickets, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "ticket_data": ticket_data,
            "pagination_info": pagination_info,
        }
    )


@router.get("/stats")
async def get_ticket_stats(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    pipeline = []
    pipeline.append(
        {
            "$group": {
                "_id": None,
                "OPEN": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", TicketStatusData.OPEN]},
                            1,
                            0,
                        ]
                    }
                },
                "PENDING": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", TicketStatusData.PENDING]}, 1, 0]
                    }
                },
                "ON_PROGRESS": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", TicketStatusData.ON_PROGRESS]},
                            1,
                            0,
                        ]
                    }
                },
                "CLOSED": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", TicketStatusData.CLOSED]}, 1, 0]
                    }
                },
                "count": {"$sum": 1},
            }
        }
    )
    ticket_stats_data, _ = await GetManyData(db.tickets, pipeline)
    return JSONResponse(content={"ticket_stats_data": ticket_stats_data[0]})


@router.post("/add")
async def create_ticket(
    data: TicketInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = f'{payload["type"].value}-{int(GetCurrentDateTime().timestamp())}'
    payload["status"] = TicketStatusData.OPEN
    payload["id_assignee"] = ObjectId(payload["id_assignee"])
    if "id_reporter" in payload and payload["id_reporter"]:
        payload["id_reporter"] = ObjectId(payload["id_reporter"])
    if "id_odc" in payload and payload["id_odc"] is not None:
        payload["id_odc"] = ObjectId(payload["id_odc"])
    if "id_odp" in payload and payload["id_odp"] is not None:
        payload["id_odp"] = ObjectId(payload["id_odp"])

    payload["created_at"] = GetCurrentDateTime()
    payload["created_by"] = ObjectId(current_user.id)
    result = await CreateOneData(db.tickets, payload)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    await SendWhatsappTicketOpenMessage(db, str(result.inserted_id))
    await SendTelegramTicketOpenMessage(db, str(result.inserted_id))

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_ticket(
    id: str,
    data: TicketUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    if "id_reporter" in payload and payload["id_reporter"]:
        payload["id_reporter"] = ObjectId(payload["id_reporter"])
    if "id_assignee" in payload:
        payload["id_assignee"] = ObjectId(payload["id_assignee"])
    if "id_odc" in payload and payload["id_odc"] is not None:
        payload["id_odc"] = ObjectId(payload["id_odc"])
    if "id_odp" in payload and payload["id_odp"] is not None:
        payload["id_odp"] = ObjectId(payload["id_odp"])

    exist_data = await GetOneData(db.tickets, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    payload["updated_at"] = GetCurrentDateTime()
    payload["updated_by"] = ObjectId(current_user.id)
    result = await UpdateOneData(db.tickets, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    if (
        "id_assignee" in payload
        and "id_assignee" in exist_data
        and exist_data["id_assignee"] != str(payload["id_assignee"])
    ) or ("id_assignee" not in exist_data):
        notification_data = {
            "title": exist_data["title"],
            "id_user": payload["id_assignee"],
            "description": exist_data["description"],
            "type": NotificationTypeData.TICKET.value,
            "is_read": 0,
            "id_reporter": ObjectId(exist_data["id_reporter"]),
            "created_at": GetCurrentDateTime(),
        }
        await CreateOneData(db.notifications, notification_data)

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/close/{id}")
async def close_ticket(
    id: str,
    data: None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.tickets, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})
    return "masuk"


@router.delete("/delete/{id}")
async def delete_ticket(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.tickets, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.tickets, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
