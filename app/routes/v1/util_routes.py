from fastapi import (
    APIRouter,
    HTTPException,
    File,
    Request,
    UploadFile,
)
from app.models.generals import UploadImageType
from app.modules.generals import GetCurrentDateTime
from pathlib import Path
import shutil
from app.modules.telegram_message import SendTelegramImage
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CUSTOMER_PASSWORD = os.getenv("DEFAULT_CUSTOMER_PASSWORD")
STATIC_DIR = Path("assets")
STATIC_DIR.mkdir(parents=True, exist_ok=True)


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


@router.get("/test")
async def test():
    await SendTelegramImage(
        [
            "https://api.amreta.net/assets/id-card-attachment/id-card-attachment-1738079198.jpeg"
        ],
        5,
    )
