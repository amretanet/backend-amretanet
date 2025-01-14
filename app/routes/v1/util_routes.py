from fastapi import (
    APIRouter,
    HTTPException,
    File,
    Request,
    UploadFile,
)
from fastapi.params import Depends
from app.models.generals import UploadImageType
from app.modules.generals import GetCurrentDateTime
from pathlib import Path
import shutil
import os
from dotenv import load_dotenv
from app.modules.database import (
    AsyncIOMotorClient,
    GetAmretaDatabase,
    GetLocalhostDatabase,
)
from app.modules.crud_operations import CreateManyData, GetManyData

load_dotenv()

DEFAULT_CUSTOMER_PASSWORD = os.getenv("DEFAULT_CUSTOMER_PASSWORD")
STATIC_DIR = Path("assets")
STATIC_DIR.mkdir(parents=True, exist_ok=True)


async def get_all_data(v_db_collection, v_query: list = []):
    result = await v_db_collection.aggregate(v_query).to_list(None)
    return result


router = APIRouter(prefix="/utility", tags=["Utility"])


@router.post("/upload-file/{type}")
async def upload_file(
    request: Request,
    type: UploadImageType,
    file: UploadFile = File(...),
):
    file_name = type.value.lower().replace("_", "-")
    new_filename = f"{file_name}-{round(GetCurrentDateTime().timestamp())}{Path(file.filename).suffix}"
    file_path = STATIC_DIR / type.value.lower().replace("_", "-") / new_filename
    base_url = f"{request.url.scheme}://{request.headers['host']}"
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_url = f"{base_url}/{STATIC_DIR}/{type.value.lower().replace('_', '-')}/{new_filename}"
        return {"file_url": file_url}
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"message": "Terjadi Kesalahan Pada Proses Upload Gambar"},
        )


@router.get("/migrations")
async def migration_data(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
    db_localhost: AsyncIOMotorClient = Depends(GetLocalhostDatabase),
):
    users = await get_all_data(db_localhost.users)
    await CreateManyData(db.users, users)
    area_provinces = await get_all_data(db_localhost.area_provinces)
    await CreateManyData(db.area_provinces, area_provinces)
    area_regency = await get_all_data(db_localhost.area_regency)
    await CreateManyData(db.area_regency, area_regency)
    area_subdistrict = await get_all_data(db_localhost.area_subdistrict)
    await CreateManyData(db.area_subdistrict, area_subdistrict)
    area_village = await get_all_data(db_localhost.area_village)
    await CreateManyData(db.area_village, area_village)
    configurations = await get_all_data(db_localhost.configurations)
    await CreateManyData(db.configurations, configurations)
    coverage_areas = await get_all_data(db_localhost.coverage_areas)
    await CreateManyData(db.coverage_areas, coverage_areas)
    hardwares = await get_all_data(db_localhost.hardwares)
    await CreateManyData(db.hardwares, hardwares)
    odc = await get_all_data(db_localhost.odc)
    await CreateManyData(db.odc, odc)
    odp = await get_all_data(db_localhost.odp)
    await CreateManyData(db.odp, odp)
    packages = await get_all_data(db_localhost.packages)
    await CreateManyData(db.packages, packages)
    router = await get_all_data(db_localhost.router)
    await CreateManyData(db.router, router)

    return "Telah Diupdate"
