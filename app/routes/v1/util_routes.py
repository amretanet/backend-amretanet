from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    File,
    Request,
    UploadFile,
)
from fastapi.responses import JSONResponse
from app.models.users import UserData
from app.models.generals import UploadImageType
from app.modules.generals import GetCurrentDateTime
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import GetManyData
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from pathlib import Path
import shutil

STATIC_DIR = Path("assets/images")
STATIC_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/utility", tags=["Utility"])


@router.post("/upload-image/{type}")
async def upload_file(
    request: Request,
    type: UploadImageType,
    file: UploadFile = File(...),
    current_user: UserData = Depends(GetCurrentUser),
):
    new_filename = f"{type.value.lower()}-{GetCurrentDateTime().timestamp()}{Path(file.filename).suffix}"
    file_path = STATIC_DIR / type.value.lower() / new_filename
    base_url = f"{request.url.scheme}://{request.headers['host']}"
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_url = f"{base_url}/{STATIC_DIR}/{type.value.lower()}/{new_filename}"
        return {"file_url": file_url}
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"message": "Terjadi Kesalahan Pada Proses Upload Gambar"},
        )


@router.get("/odc-options")
async def get_odc_options(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    ODCOptionsProjections = {"_id": 0, "title": "$name", "value": "$_id"}
    odc_options, _ = await GetManyData(db.odc, [], ODCOptionsProjections)
    return JSONResponse(content={"odc_options": odc_options})
