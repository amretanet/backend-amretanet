from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.models.customers import CustomerInsertData
from app.models.informations import InformationType
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


router = APIRouter(prefix="/customer", tags=["Customers"])


@router.get("")
async def get_customers(
    type: InformationType,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {"type": type}
    configuration_data = await GetOneData(db.configurations, query)
    if not configuration_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    return JSONResponse(content={"configuration_data": configuration_data})


@router.post("/add")
async def create_customer(
    data: CustomerInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    return "masuk"


@router.put("/update")
async def update_customer(
    type: InformationType = Body(..., embed=True),
    text: str = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    update_data = {"text": text, "updated_at": GetCurrentDateTime()}
    result = await UpdateOneData(
        db.configurations, {"type": type}, {"$set": update_data}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})
