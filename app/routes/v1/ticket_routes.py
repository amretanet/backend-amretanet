import asyncio
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
from app.modules.whatsapp_message import (
    SendWhatsappTicketClosedMessage,
    SendWhatsappTicketOpenMessage,
)
from app.modules.telegram_message import (
    SendTelegramTicketClosedMessage,
    SendTelegramTicketOpenMessage,
)
from app.models.notifications import NotificationTypeData
from app.models.tickets import (
    TicketCloseData,
    TicketInsertData,
    TicketPendingData,
    TicketStatusData,
    TicketTypeData,
    TicketUpdateData,
)
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

router = APIRouter(prefix="/ticket", tags=["Tickets"])


@router.get("")
async def get_tickets(
    key: str = None,
    status: TicketStatusData = None,
    id_reporter: str = None,
    id_assignee: str = None,
    created_by: str = None,
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
    if id_reporter:
        query["id_reporter"] = ObjectId(id_reporter)
    if id_assignee:
        query["id_assignee"] = ObjectId(id_assignee)
    if created_by:
        query["created_by"] = ObjectId(created_by)

    pipeline = [
        {"$match": query},
        {
            "$addFields": {
                "status_priority": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {
                                    "$eq": [
                                        "$status",
                                        TicketStatusData.ON_PROGRESS.value,
                                    ]
                                },
                                "then": 1,
                            },
                            {
                                "case": {
                                    "$eq": ["$status", TicketStatusData.OPEN.value]
                                },
                                "then": 2,
                            },
                            {
                                "case": {
                                    "$eq": ["$status", TicketStatusData.PENDING.value]
                                },
                                "then": 3,
                            },
                            {
                                "case": {
                                    "$eq": ["$status", TicketStatusData.CLOSED.value]
                                },
                                "then": 4,
                            },
                        ],
                        "default": 5,
                    }
                }
            }
        },
        {
            "$sort": {
                "status_priority": 1,
                "created_at": 1,
            }
        },
        {
            "$lookup": {
                "from": "users",
                "let": {"idReporter": "$id_reporter"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idReporter"]}}},
                    {"$project": {"name": 1}},
                ],
                "as": "reporter",
            }
        },
        {
            "$lookup": {
                "from": "users",
                "let": {"idAssignee": "$id_assignee"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idAssignee"]}}},
                    {"$project": {"name": 1}},
                ],
                "as": "assignee",
            }
        },
        {
            "$lookup": {
                "from": "odc",
                "let": {"idOdc": "$id_odc"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idOdc"]}}},
                    {"$project": {"name": 1}},
                ],
                "as": "odc",
            }
        },
        {
            "$lookup": {
                "from": "odp",
                "let": {"idOdp": "$id_odp"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idOdp"]}}},
                    {"$project": {"name": 1}},
                ],
                "as": "odp",
            }
        },
        {
            "$lookup": {
                "from": "users",
                "let": {"createdBy": "$created_by"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$createdBy"]}}},
                    {"$project": {"name": 1}},
                ],
                "as": "creator",
            }
        },
        {
            "$lookup": {
                "from": "customers",
                "let": {"idReporter": "$id_reporter"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$id_user", "$$idReporter"]}}},
                    {"$limit": 1},
                ],
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
    id_reporter: str = None,
    id_assignee: str = None,
    created_by: str = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if id_reporter:
        query["id_reporter"] = ObjectId(id_reporter)
    if id_assignee:
        query["id_assignee"] = ObjectId(id_assignee)
    if created_by:
        query["created_by"] = ObjectId(created_by)
    pipeline = []
    pipeline.append({"$match": query})
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
    ticket_stats_data = await GetAggregateData(db.tickets, pipeline)
    return JSONResponse(
        content={
            "ticket_stats_data": ticket_stats_data[0]
            if len(ticket_stats_data) > 0
            else []
        }
    )


@router.post("/add")
async def create_ticket(
    data: TicketInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = f"{payload['type'].value}-{int(GetCurrentDateTime().timestamp())}"
    payload["status"] = TicketStatusData.OPEN
    notification_data = {}
    if "id_reporter" in payload and payload["id_reporter"]:
        payload["id_reporter"] = ObjectId(payload["id_reporter"])
        exist_reporter = await GetOneData(
            db.tickets,
            {
                "id_reporter": payload["id_reporter"],
                "status": {"$ne": TicketStatusData.CLOSED.value},
            },
        )
        if exist_reporter:
            raise HTTPException(
                status_code=400,
                detail={"message": "Tiket Pada Pelanggan Tersebut Belum Selesai!"},
            )
    if "id_assignee" in payload and payload["id_assignee"]:
        payload["id_assignee"] = ObjectId(payload["id_assignee"])
        notification_data = {
            "id_user": payload["id_assignee"],
            "title": f"Tiket {payload['name']} OPEN",
            "description": payload["title"],
            "type": NotificationTypeData.TICKET.value,
            "is_read": 0,
            "created_at": GetCurrentDateTime(),
        }
    if "id_odc" in payload and payload["id_odc"] is not None:
        payload["id_odc"] = ObjectId(payload["id_odc"])
    if "id_odp" in payload and payload["id_odp"] is not None:
        payload["id_odp"] = ObjectId(payload["id_odp"])

    payload["created_at"] = GetCurrentDateTime()
    payload["created_by"] = ObjectId(current_user.id)
    result = await CreateOneData(db.tickets, payload)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    if notification_data:
        await CreateOneData(db.notifications, notification_data)

    asyncio.create_task(SendWhatsappTicketOpenMessage(db, str(result.inserted_id)))
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
    exist_data = await GetOneData(db.tickets, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    if "id_reporter" in payload and payload["id_reporter"]:
        payload["id_reporter"] = ObjectId(payload["id_reporter"])
        exist_reporter = await GetOneData(
            db.tickets,
            {
                "_id": {"$ne": ObjectId(id)},
                "id_reporter": payload["id_reporter"],
                "status": {"$ne": TicketStatusData.CLOSED.value},
            },
        )
        if exist_reporter:
            raise HTTPException(
                status_code=400,
                detail={"message": "Tiket Pada Pelanggan Tersebut Belum Selesai!"},
            )
    if "id_assignee" in payload:
        if payload["id_assignee"] != exist_data.get("id_assignee"):
            payload["status"] = TicketStatusData.OPEN.value

        payload["id_assignee"] = ObjectId(payload["id_assignee"])
    if "id_odc" in payload and payload["id_odc"] is not None:
        payload["id_odc"] = ObjectId(payload["id_odc"])
    if "id_odp" in payload and payload["id_odp"] is not None:
        payload["id_odp"] = ObjectId(payload["id_odp"])

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
            "id_user": payload["id_assignee"],
            "title": f"Tiket {exist_data.get('name', '')} {payload['status'] if 'status' in payload else exist_data.get('status', 'OPEN')}",
            "description": payload["title"]
            if "title" in payload
            else exist_data.get("title", ""),
            "type": NotificationTypeData.TICKET.value,
            "is_read": 0,
            "created_at": GetCurrentDateTime(),
        }
        await CreateOneData(db.notifications, notification_data)
        asyncio.create_task(
            SendWhatsappTicketOpenMessage(db, exist_data["_id"], is_only_assignee=True)
        )

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/pending/{id}")
async def pending_ticket(
    id: str,
    data: TicketPendingData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.tickets, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    payload["status"] = TicketStatusData.PENDING.value
    result = await UpdateOneData(db.tickets, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/close/{id}")
async def close_ticket(
    id: str,
    data: TicketCloseData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True, exclude_none=True)
    payload["status"] = TicketStatusData.CLOSED.value
    payload["closed_at"] = GetCurrentDateTime()
    exist_data = await GetOneData(db.tickets, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    customer_update_data = {}
    if payload.get("id_odc"):
        payload["id_odc"] = ObjectId(payload["id_odc"])
    if payload.get("id_odp"):
        payload["id_odp"] = ObjectId(payload["id_odp"])
        customer_update_data["id_odp"] = payload["id_odp"]

    result = await UpdateOneData(db.tickets, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    if (
        exist_data.get("type") == TicketTypeData.PSB.value
        or payload.get("type") == TicketTypeData.PSB.value
    ):
        await UpdateOneData(
            db.customers,
            {"id_user": ObjectId(exist_data.get("id_reporter"))},
            {"$set": customer_update_data},
        )

    notification_data = {
        "title": f"Tiket {exist_data.get('name', '')} {payload['status']}",
        "description": "Tiket Telah Selesai Dikerjakan",
        "type": NotificationTypeData.TICKET.value,
        "is_read": 0,
        "created_at": GetCurrentDateTime(),
    }
    id_creator = exist_data.get("created_by", None)
    id_reporter = exist_data.get("id_reporter", None)
    if id_creator != id_reporter:
        notification_data["id_user"] = ObjectId(id_creator)
        await CreateOneData(db.notifications, notification_data.copy())

    admin_user = await GetAggregateData(
        db.users, [{"$match": {"role": UserRole.ADMIN}}]
    )
    if len(admin_user) > 0:
        for user in admin_user:
            if user["_id"] != id_creator:
                notification_data["id_user"] = ObjectId(user["_id"])
                await CreateOneData(db.notifications, notification_data.copy())

    asyncio.create_task(SendWhatsappTicketClosedMessage(db, id))
    await SendTelegramTicketClosedMessage(db, id)

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


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
