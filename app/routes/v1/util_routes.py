import json
from bson import json_util
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    File,
    Request,
    UploadFile,
)
from app.models.generals import UploadImageType
from app.modules.generals import GetCurrentDateTime
from pathlib import Path
import shutil
from app.modules.crud_operations import GetOneData, UpdateOneData
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
import os
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CUSTOMER_PASSWORD = os.getenv("DEFAULT_CUSTOMER_PASSWORD")
STATIC_DIR = Path("assets")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR = os.getenv("BACKUP_DIR")

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    base_url = f"https://{request.headers['host']}"
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


@router.get("/reset-unique-code")
async def reset_unique_code(db: AsyncIOMotorClient = Depends(GetAmretaDatabase)):
    result = await UpdateOneData(
        db.configurations, {"type": "INVOICE_UNIQUE_CODE"}, {"$set": {"value": 1}}
    )
    return result


@router.get("/backup")
async def backup_data(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    collections = await db.list_collection_names()

    for collection_name in collections:
        collection = db[collection_name]
        documents = await collection.find().to_list(None)
        if len(documents) == 0:
            continue

        backup_filename = f"{BACKUP_DIR}/{collection_name}.json"
        with open(backup_filename, "w", encoding="utf-8") as f:
            json.dump(
                documents, f, indent=4, default=json_util.default, ensure_ascii=False
            )

    return {"message": "Backup berhasil", "file": backup_filename}


@router.get("/restore")
async def restore_data(
    file_path: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        for collection_name, documents in backup_data.items():
            collection = db[collection_name]
            if documents:
                await collection.insert_many(documents)

        return {"message": "Restore berhasil"}

    except Exception as e:
        return {"error": str(e)}
