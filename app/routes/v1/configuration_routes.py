from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.models.configurations import (
    ConfigurationType,
    EmailBotUpdateData,
    WhatsappBotUpdateData,
    MapsApiUpdateData,
    TelegramBotUpdateData,
)
from app.models.users import UserData
from app.modules.crud_operations import GetOneData, UpdateOneData
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import GetCurrentDateTime
from app.modules.response_message import (
    DATA_HAS_UPDATED_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
)
from app.routes.v1.auth_routes import GetCurrentUser


router = APIRouter(prefix="/configuration", tags=["Configurations"])


@router.get("")
async def get_system_configurations(
    type: ConfigurationType,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {"type": type}
    configuration_data = await GetOneData(db.configurations, query)
    if not configuration_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    return JSONResponse(content={"configuration_data": configuration_data})


@router.put("/maps-api/update")
async def update_maps_api(
    data: MapsApiUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    update_data = data.dict(exclude_unset=True)
    update_data["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(
        db.configurations, {"type": "GOOGLE_MAPS_API"}, {"$set": update_data}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/telegram-bot/update")
async def update_telegram_bot(
    data: TelegramBotUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    update_data = data.dict(exclude_unset=True)
    update_data["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(
        db.configurations, {"type": "TELEGRAM_BOT"}, {"$set": update_data}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/email-bot/update")
async def update_email_bot(
    data: EmailBotUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    update_data = data.dict(exclude_unset=True)
    update_data["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(
        db.configurations, {"type": "EMAIL_BOT"}, {"$set": update_data}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/whatsapp-bot/update")
async def update_whatsapp_bot(
    data: WhatsappBotUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    update_data = data.dict(exclude_unset=True)
    update_data["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(
        db.configurations, {"type": "WHATSAPP_BOT"}, {"$set": update_data}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})
