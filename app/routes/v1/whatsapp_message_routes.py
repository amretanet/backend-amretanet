from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
)
from app.models.whatsapp_messages import (
    AdvanceMessageTemplateData,
    SendBroadcastMessageData,
    SendSingleMessageData,
)
from app.modules.whatsapp_message import SendWhatsappMessage, WhatsappMessageFormatter
from app.models.customers import CustomerStatusData
from app.modules.response_message import (
    DATA_FORMAT_NOT_VALID_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from fastapi.responses import JSONResponse
from app.models.users import UserData
from app.models.generals import Pagination
from app.modules.generals import ReminderDateFormatter
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import (
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
import os
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_BOT_NUMBER = os.getenv("WHATSAPP_BOT_NUMBER")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY")

router = APIRouter(prefix="/whatsapp-message", tags=["Whatsapp Messages"])


@router.get("/template")
async def get_message_template(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    template_data = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if not template_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    return JSONResponse(content={"template_data": template_data})


@router.put("/template/update/{type}")
async def update_message_template(
    type: str,
    message: str = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    template_data = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if not template_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    update_data = {type: message}
    result = await UpdateOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}, {"$set": update_data}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/template/advance-update")
async def update_advance_message_template(
    data: AdvanceMessageTemplateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    template_data = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if not template_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await UpdateOneData(
        db.configurations,
        {"type": "WHATSAPP_MESSAGE_TEMPLATE"},
        {"$set": {"advance": payload}},
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.get("/reminder")
async def get_reminder(
    key: str = None,
    page: int = 1,
    items: int = 10,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {
        "status": CustomerStatusData.active.value,
    }
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
            {
                "$expr": {
                    "$regexMatch": {
                        "input": {"$toString": "$service_number"},
                        "regex": key,
                        "options": "i",
                    }
                }
            },
        ]

    pipeline = [
        {"$match": query},
        {"$sort": {"name": 1}},
        {
            "$project": {
                "name": 1,
                "service_number": 1,
                "phone_number": 1,
                "due_date": 1,
            }
        },
    ]

    customer_data, count = await GetManyData(
        db.customers, pipeline, {}, {"page": page, "items": items}
    )
    for item in customer_data:
        if "due_date" in item:
            remind_at = ReminderDateFormatter(item["due_date"])
            item["remind_at"] = remind_at

    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "customer_data": customer_data,
            "pagination_info": pagination_info,
        }
    )


@router.post("/single/send")
async def send_single_message(
    data: SendSingleMessageData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        payload = data.dict(exclude_unset=True)
        response = await SendWhatsappMessage(
            payload["destination"],
            WhatsappMessageFormatter(payload["title"], payload["message"]),
        )
        if response.status_code == 200:
            return JSONResponse(content={"message": "Pesan Telah Dikirimkan!"})

        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.post("/broadcast/send")
async def send_broadcast_message(
    data: SendBroadcastMessageData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        payload = data.dict(exclude_unset=True)
        contact_data = []
        if payload["group"] == "user":
            query = {}
            if payload["destination"] != "all":
                query["role"] = int(payload["destination"])

            user_data, _ = await GetManyData(db.users, [{"$match": query}])
            contact_data = user_data
        elif payload["group"] == "package":
            query = {"id_package": ObjectId(payload["destination"])}
            customer_data, _ = await GetManyData(db.customers, [{"$match": query}])
            contact_data = customer_data
        elif payload["group"] == "coverage_area":
            query = {"id_coverage_area": ObjectId(payload["destination"])}
            customer_data, _ = await GetManyData(db.customers, [{"$match": query}])
            contact_data = customer_data
        elif payload["group"] == "odp":
            query = {"id_odp": ObjectId(payload["destination"])}
            customer_data, _ = await GetManyData(db.customers, [{"$match": query}])
            contact_data = customer_data
        else:
            raise HTTPException(
                status_code=400, detail={"message": DATA_FORMAT_NOT_VALID_MESSAGE}
            )

        if len(contact_data) == 0:
            raise HTTPException(
                status_code=404,
                detail={"message": "Daftar Kontak Tujuan Tidak Ditemukan!"},
            )

        for item in contact_data:
            await SendWhatsappMessage(
                item["phone_number"],
                WhatsappMessageFormatter(payload["title"], payload["message"]),
            )

        return JSONResponse(content={"message": "Pesan Telah Dikirimkan!"})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})
