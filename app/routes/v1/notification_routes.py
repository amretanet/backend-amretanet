from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from fastapi.responses import JSONResponse
from app.models.notifications import NotificationTypeData
from app.models.users import UserData
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import (
    DeleteManyData,
    DeleteOneData,
    GetDataCount,
    GetManyData,
    GetOneData,
    UpdateManyData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)

router = APIRouter(prefix="/notification", tags=["Notifications"])


@router.get("")
async def get_notifications(
    type: NotificationTypeData = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    pipeline = []
    if type:
        pipeline.append({"$match": {"type": type.value}})

    pipeline.append({"$sort": {"created_at": -1}})

    notification_data, _ = await GetManyData(db.notifications, pipeline)
    notification_count = await GetDataCount(db.notifications, {"is_read": 0})
    return JSONResponse(
        content={
            "notification_data": notification_data,
            "notification_count": notification_count,
        }
    )


@router.put("/read/{id}")
async def read_notification(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.notifications, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await UpdateOneData(
        db.notifications, {"_id": ObjectId(id)}, {"$set": {"is_read": 1}}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/read-all")
async def read_all_notification(
    type: NotificationTypeData,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    result = await UpdateManyData(
        db.notifications, {"type": type.value}, {"$set": {"is_read": 1}}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_notification(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.notifications, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.notifications, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})


@router.delete("/delete-all")
async def delete_all_notification(
    type: NotificationTypeData,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    result = await DeleteManyData(db.notifications, {"type": type.value})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
