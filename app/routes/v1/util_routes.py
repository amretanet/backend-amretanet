from urllib.parse import urlencode
from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    File,
    Request,
    UploadFile,
)
from app.modules.response_message import NOT_FOUND_MESSAGE
from fastapi.responses import JSONResponse
from app.models.users import UserData
from app.models.generals import UploadImageType
from app.modules.generals import GetCurrentDateTime
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import (
    CreateOneData,
    GetManyData,
    GetOneData,
    UpdateManyData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from pathlib import Path
import shutil
import requests
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

STATIC_DIR = Path("assets/images")
STATIC_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/utility", tags=["Utility"])


@router.get("/process-data")
async def process_data(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    # odc_data, _ = await GetManyData(db.odc, [])
    # for item in odc_data:
    #     update_data = {
    #         "location.latitude": item["location"]["longitude"],
    #         "location.longitude": item["location"]["latitude"],
    #     }
    #     print(update_data)
    #     await UpdateManyData(
    #         db.odc, {"_id": ObjectId(item["_id"])}, {"$set": update_data}
    #     )
    # UPDATE CUSTOMERS
    # cust_data, _ = await GetManyData(db.customers, [])
    # for item in cust_data:
    #     update_data = {}
    #     update_data["due_date"] = str(int(item["due_date"])).zfill(2)
    #     # if item["status"].lower() == "aktif":
    #     #     update_data["status"] = 1
    #     # if item["status"].lower() == "non-aktif":
    #     #     update_data["status"] = 0
    #     # if item["status"].lower() == "menunggu":
    #     #     update_data["status"] = 2
    #     # if item["status"].lower() == "gratis":
    #     #     update_data["status"] = 3
    #     # if item["status"].lower() == "isolir":
    #     #     update_data["status"] = 4
    #     # router_data = await GetOneData(db.router,{"name":item["id_router"]})
    #     # if router_data:
    #     #     update_data["id_router"] = ObjectId(router_data["_id"])
    #     # odp = await GetOneData(db.odp, {"name": item["id_odp"]})
    #     # if odp:
    #     #     update_data["id_odp"] = ObjectId(odp["_id"])

    #     # coverage_area = await GetOneData(
    #     #     db.coverage_areas, {"old_id": item["id_coverage_area"]}
    #     # )
    #     # if coverage_area:
    #     #     update_data["id_coverage_area"] = ObjectId(coverage_area["_id"])

    #     # package = await GetOneData(db.packages, {"old_id": item["id_package"]})
    #     # if package:
    #     #     update_data["id_package"] = ObjectId(package["_id"])

    #     await UpdateOneData(
    #         db.customers, {"_id": ObjectId(item["_id"])}, {"$set": update_data}
    #     )
    # old_data, _ = await GetManyData(db.temp_customer, [])
    # for item in old_data:
    #     customer_data = {
    #         "old_id": item["customer_id"],
    #         "name": item["name"],
    #         "service_number": item["no_services"],
    #         "id_card": {
    #             "type": item["type_id"],
    #             "number": item["no_ktp"],
    #             "image_url": item["ktp"],
    #         },
    #         "gender": None,
    #         "email": item["email"],
    #         "phone_number": str(item["no_wa"]),
    #         "location": {
    #             "house_status": item["statusrumah"]
    #             if "statusrumah" in item
    #             else "Pribadi",
    #             "house_owner": item["pemilik_rumah"] if "pemilik_rumah" in item else None,
    #             "address": item["address"],
    #             "latitude": item["latitude"]
    #             if "latitude" in item
    #             else -6.942853679893406,
    #             "longitude": item["longitude"]
    #             if "longitude" in item
    #             else 107.76403158903122,
    #         },
    #         "description": "Input By Website",
    #         "billing_type": item["jenis"] if "jenis" in item else "PASCABAYAR",
    #         "ppn": item["ppn"],
    #         "due_date": str(item["due_date"]) if "due_date" in item else None,
    #         "unique_code": item["code_unique"] if "code_unique" in item else None,
    #         "referal_code": item["refferal"] if "referral" in item else None,
    #         "id_router": item["router"] if "router" in item else None,
    #         "id_package": item["item_paket"] if "item_paket" in item else None,
    #         "id_coverage_area": item["coverage"] if "coverage" in item else None,
    #         "id_odp": item["kode_odp"] if "kode_odp" in item else None,
    #         "port_odp": item["port_odp"] if "port_odp" in item else 0,
    #         "status": item["c_status"] if "c_status" in item else 1,
    #         "time_stamp": item["created"] if "created" in item else None,
    #     }
    #     user_data = {
    #         "name": item["name"],
    #         "email": item["email"],
    #         "password": pwd_context.hash("pelanggan"),
    #         "phone_number": item["no_wa"],
    #         "status": item["c_status"],
    #         "gender": None,
    #         "saldo": 0,
    #         "role": 99,
    #         "address": item["address"],
    #     }
    #     result = await CreateOneData(db.users,user_data)
    #     if result.inserted_id:
    #         customer_data["id_user"] = result.inserted_id
    #         await CreateOneData(db.customers, customer_data)

    return "berhasil"
    # UPDATE PACKAGE
    # old_data, _ = await GetManyData(db.temp_package, [])
    # for item in old_data:
    #     package_data = {
    #         "old_id": item["p_item_id"],
    #         "name": item["name"],
    #         "router_profile": item["paket_wifi"],
    #         "bandwidth": 0,
    #         "instalation_cost": 0,
    #         "maximum_device": 0,
    #         "price": {"regular": item["price"], "reseller": item["reseller"]},
    #         "is_displayed": item["public"],
    #         "description": item["description"] if "description" in item else "",
    #     }
    #     await CreateOneData(db.packages, package_data)

    # return "selesai"
    # UPDATE AREA
    # odp_data, _ = await GetManyData(db.odp, [])
    # for item in odp_data:
    #     await UpdateOneData(
    #         db.odp,
    #         {"_id": ObjectId(item["_id"])},
    #         {"$set": {"damping": str(item["damping"])}},
    #     )
    # return "masuk"
    # old_area, _ = await GetManyData(
    #     db.temp_coverage, [{"$match": {"kategori": "AREA"}}]
    # )
    # for item in old_area:
    #     area_data = {
    #         "old_id": item["coverage_id"],
    #         "name": item["c_name"].strip(),
    #         "address": {
    #             "province": "Jawa Barat",
    #             "regency": "Sumedang",
    #             "subdistrict": "Jatinangor",
    #             "village": "Cipacing",
    #             "rw": item["nomor_rw"],
    #             "rt": item["nomor_rt"],
    #             "location_name": None,
    #             "postal_code": item["kode_pos"],
    #             "latitude": item["latitude"],
    #             "longitude": item["longitude"],
    #         },
    #         "capacity": item["kapasitas"],
    #         "available": item["tersedia"],
    #     }
    #     await CreateOneData(db.coverage_areas, area_data)
    # return old_area
    # UPDATE ODP
    # old_odp, _ = await GetManyData(db.temp_coverage, [{"$match": {"kategori": "ODP"}}])
    # for item in old_odp:
    #     odp_data = {
    #         "old_id": item["coverage_id"],
    #         "id_parent": None,
    #         "name": item["c_name"].strip(),
    #         "image_url": "",
    #         "location": {
    #             "address": item["address"].strip(),
    #             "longitude": item["latitude"],
    #             "latitude": item["longitude"],
    #         },
    #         "port": item["port_pon"],
    #         "capacity": item["kapasitas"],
    #         "available": item["tersedia"],
    #         "damping": item["redaman"],
    #         "tube": item["tube"],
    #         "description": item["comment"],
    #     }
    #     await CreateOneData(db.odp, odp_data)
    # return old_odp

    # UPDATE ODC
    # old_odc, _ = await GetManyData(db.temp_coverage, [{"$match": {"kategori": "ODC"}}])
    # for item in old_odc:
    #     odc_data = {
    #         "old_id": item["coverage_id"],
    #         "name": item["c_name"].strip(),
    #         "image_url": "",
    #         "location": {
    #             "address": item["complete"].strip(),
    #             "longitude": item["latitude"],
    #             "latitude": item["longitude"],
    #         },
    #         "port": item["port_pon"],
    #         "capacity": item["kapasitas"],
    #         "available": item["tersedia"],
    #         "damping": item["redaman"],
    #         "tube": item["tube"],
    #         "description": item["comment"],
    #     }
    #     await CreateOneData(db.odc,odc_data)
    return "masuk"


@router.post("/upload-image/{type}")
async def upload_file(
    request: Request,
    type: UploadImageType,
    file: UploadFile = File(...),
):
    file_name = type.value.lower().replace("_", "-")
    new_filename = (
        f"{file_name}-{GetCurrentDateTime().timestamp()}{Path(file.filename).suffix}"
    )
    file_path = STATIC_DIR / type.value.lower().replace("_", "-") / new_filename
    base_url = f"{request.url.scheme}://{request.headers['host']}"
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_url = f"{base_url}/{STATIC_DIR}/{type.value.lower().replace("_", "-")}/{new_filename}"
        return {"file_url": file_url}
    except Exception:
        raise HTTPException(
            status_code=500,
            detail={"message": "Terjadi Kesalahan Pada Proses Upload Gambar"},
        )


@router.get("/send-message")
async def send_message(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
    if not whatsapp_bot:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    # api_url = whatsapp_bot
    # return whatsapp_bot

    API_URL = "https://wa7.amretanet.my.id/send-message"
    API_TOKEN = "hVJpEdxZ1cNUHhRuKfGTa552RdOVZp"

    # Parameter Query
    params = {
        "api_key": API_TOKEN,
        "sender": "6285159979915",
        "number": "6281218030424",
        "message": "Hello World",
    }

    # Buat URL dengan Query String
    final_url = f"{API_URL}?{urlencode(params)}"
    response = requests.get(final_url)
    return response.json()


@router.get("/send-media")
async def send_media(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    API_URL = "https://wa7.amretanet.my.id/send-media"
    API_TOKEN = "hVJpEdxZ1cNUHhRuKfGTa552RdOVZp"

    # Parameter Query
    params = {
        "api_key": API_TOKEN,
        "sender": "085159979915",
        "number": "081218030424",
        "media_type": "document",
        "caption": "Hello World",
        "url": "http://127.0.0.1:8000/assets/pdf/TRANSKRIP.pdf",
    }

    # Buat URL dengan Query String
    final_url = f"{API_URL}?{urlencode(params)}"
    response = requests.get(final_url)
    return response.json()
