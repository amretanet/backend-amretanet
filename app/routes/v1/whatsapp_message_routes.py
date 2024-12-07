from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
)
from urllib.parse import urlencode, urljoin
from app.models.whatsapp_messages import (
    AdvanceMessageTemplateData,
    SendMessageData,
    SendMessageType,
)
from app.models.packages import PackageInsertData
from app.modules.response_message import (
    DATA_FORMAT_NOT_VALID_MESSAGE,
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from fastapi.responses import JSONResponse
from app.models.users import UserData
from app.models.generals import Pagination
from app.modules.generals import GetCurrentDateTime, ReminderDateFormatter
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
import requests

router = APIRouter(prefix="/whatsapp-message", tags=["Whatsapp Brodcast"])


def MessageFormatter(message: str):
    message = message.replace("[nama_pelanggan]", "Hanhan Septian")
    return message


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
    query = {}
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


@router.post("/send-message")
async def send_message(
    data: SendMessageData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        payload = data.dict(exclude_unset=True)
        if payload["type"] == SendMessageType.broadcast and "broadcast_to" in payload:
            return "ini broadcast"
        elif payload["type"] == SendMessageType.single and "single_to" in payload:
            whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
            if not whatsapp_bot:
                raise HTTPException(
                    status_code=404, detail={"message": NOT_FOUND_MESSAGE}
                )

            API_URL = urljoin(whatsapp_bot["url_gateway"], "/send-message")
            API_TOKEN = whatsapp_bot["api_key"]

            params = {
                "api_key": API_TOKEN,
                "sender": f"62{whatsapp_bot['bot_number']}",
                "number": f"62{payload['single_to']}",
                "message": MessageFormatter(payload["message"]),
                "is_html": True,
            }
            final_url = f"{API_URL}?{urlencode(params)}"
            response = requests.post(final_url, json=params, timeout=10)
            if response.status_code == 200:
                return JSONResponse(content={"message": "Pesan Telah Dikirimkan!"})
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )
        raise HTTPException(
            status_code=400, detail={"message": DATA_FORMAT_NOT_VALID_MESSAGE}
        )
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})
