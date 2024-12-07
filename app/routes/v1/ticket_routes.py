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

router = APIRouter(prefix="/ticket", tags=["Layanan Tiket"])


@router.get("")
async def get_tickets(
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
            {"title": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
        ]

    pipeline = [
        {"$match": query},
        {"$sort": {"name": 1}},
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


@router.post("/add")
async def create_ticket(
    data: TicketInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = f"TKT-{int(GetCurrentDateTime().timestamp())}"
    payload["status"] = TicketStatusData.open
    payload["id_reporter"] = ObjectId(payload["id_reporter"])
    payload["id_assignee"] = ObjectId(payload["id_assignee"])
    if "id_odc" in payload:
        payload["id_odc"] = ObjectId(payload["id_odc"])
    if "id_odp" in payload:
        payload["id_odp"] = ObjectId(payload["id_odp"])

    payload["created_at"] = GetCurrentDateTime()
    payload["created_by"] = ObjectId(current_user.id)
    result = await CreateOneData(db.tickets, payload)
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_ticket(
    id: str,
    data: TicketUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    if "id_reporter" in payload:
        payload["id_reporter"] = ObjectId(payload["id_reporter"])
    if "id_assignee" in payload:
        payload["id_assignee"] = ObjectId(payload["id_assignee"])
    if "id_odc" in payload:
        if payload["id_odc"]:
            payload["id_odc"] = ObjectId(payload["id_odc"])
        else:
            payload["id_odc"] = None
    if "id_odp" in payload:
        if payload["id_odp"]:
            payload["id_odp"] = ObjectId(payload["id_odp"])
        else:
            payload["id_odp"] = None

    exist_data = await GetOneData(db.tickets, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    payload["updated_at"] = GetCurrentDateTime()
    payload["updated_by"] = ObjectId(current_user.id)
    result = await UpdateOneData(db.tickets, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

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
