from fastapi import APIRouter, Depends
from app.models.users import UserData, UserRole
from app.modules.crud_operations import GetManyData, GetOneData, UpdateOneData
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.routes.v1.auth_routes import GetCurrentUser
from dotenv import load_dotenv

load_dotenv()


router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("")
async def get_inventories(
    # current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    return "masuk"


@router.post("/add")
async def create_inventory(
    # current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    return "masuk"


@router.put("/update")
async def update_inventory(
    # current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    return "masuk"


@router.delete("/delete")
async def delete_inventory(
    # current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    return "masuk"
