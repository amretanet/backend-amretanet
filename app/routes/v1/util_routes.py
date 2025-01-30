from datetime import datetime
from bson import ObjectId
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    File,
    Request,
    UploadFile,
)
from app.models.users import UserRole
from app.models.customers import CustomerStatusData
from app.models.generals import UploadImageType
from app.modules.generals import GenerateReferralCode, GetCurrentDateTime
from pathlib import Path
import shutil
from app.modules.telegram_message import SendTelegramImage
from app.modules.database import (
    AsyncIOMotorClient,
    GetAmretaDatabase,
    GetLocalhostDatabase,
)
from app.modules.crud_operations import (
    CreateManyData,
    CreateOneData,
    GetOneData,
    UpdateOneData,
)
import os
import re
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CUSTOMER_PASSWORD = os.getenv("DEFAULT_CUSTOMER_PASSWORD")
STATIC_DIR = Path("assets")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def GetAggregateData(v_db_collection, v_pipeline: list = [], v_projection={}):
    pipeline = v_pipeline.copy()
    if v_projection:
        pipeline.append({"$project": v_projection})
    result = await v_db_collection.aggregate(pipeline).to_list(None)

    return result


def append_com_if_needed(url):
    # Jika string tidak diakhiri dengan ekstensi tertentu
    if not re.search(r"\.\w+$", url):  # Cek apakah ada ekstensi di akhir string
        url += ".com"
    return url


async def MigrateCustomer(db):
    customer_data = await GetAggregateData(db.temp_customers, [])
    current_data = 1
    for customer in customer_data:
        # print(current_data)
        # exist_data = await GetOneData(
        #     db.customers, {"service_number": int(customer["no_services"])}
        # )
        # if exist_data:
        #     print("sudah ada")
        #     current_data += 1
        #     continue
        data = {
            "service_number": int(customer["no_services"]),
            # "name": customer["name"],
            # "status": 0,
            # "id_card": {
            #     "type": customer["type_id"],
            #     "number": int(customer["no_ktp"]),
            #     "image_url": customer["ktp"],
            # },
            # "gender": "L",
            # "email": append_com_if_needed(customer["email"]),
            # "phone_number": str(int(customer["no_wa"])),
            # "location": {
            #     "house_status": customer["statusrumah"],
            #     "house_owner": customer["pemilik_rumah"],
            #     "house_image_url": customer["rumah"],
            #     "address": customer["complete"],
            #     "latitude": float(customer["latitude"])
            #     if customer.get("latitude")
            #     else 0,
            #     "longitude": float(customer["longitude"])
            #     if customer.get("longitude")
            #     else 0,
            # },
            # "description": customer.get("keterangan", ""),
            # "billing_type": str(customer["jenis"]).upper(),
            # "ppn": int(customer["ppn"]),
            # "due_date": customer["due_date"],
            "referral": str(customer.get("refferal"))
            if customer.get("refferal") != "0"
            else None,
            # "pppoe_username": customer["username"],
            # "pppoe_password": customer["password"],
            # "id_router": None,
            # "id_package": None,
            # "id_add_on_package": [],
            # "id_coverage_area": None,
            # "id_odp": None,
            # "port_odp": int(customer["port_odp"]) if customer.get("port_odp") else None,
            # "registered_at": datetime.strptime(customer["register_date"], "%Y-%m-%d"),
        }
        # odp = await GetOneData(db.odp, {"name": customer["kode_odp"]})
        # if odp:
        #     data["id_odp"] = ObjectId(odp["_id"])

        # router = await GetOneData(db.router, {"name": customer["router"]})
        # if router:
        #     data["id_router"] = ObjectId(router["_id"])

        # package = await GetOneData(db.packages, {"old_id": customer["item_paket"]})
        # if package:
        #     data["id_package"] = ObjectId(package["_id"])

        # coverage_area = await GetOneData(
        #     db.coverage_areas, {"old_id": customer["coverage"]}
        # )
        # if coverage_area:
        #     data["id_coverage_area"] = ObjectId(coverage_area["_id"])

        # if str(customer["c_status"]).lower() == "isolir":
        #     data["status"] = CustomerStatusData.ISOLIR.value
        # elif str(customer["c_status"]).lower() == "aktif":
        #     data["status"] = CustomerStatusData.ACTIVE.value
        # elif str(customer["c_status"]).lower() == "non-aktif":
        #     data["status"] = CustomerStatusData.NONACTIVE.value

        result = await UpdateOneData(
            db.customers,
            {"service_number": data["service_number"]},
            {"$set": data},
            upsert=True,
        )
        print(result)
    return "masuk"


async def MigrateCustomerUser(db):
    user_list = await GetAggregateData(db.temp_users, [{"$match": {"role_id": "2"}}])
    for user in user_list:
        service_number = int(user["no_services"])
        user_data = {
            "name": user["name"],
            "email": append_com_if_needed(user["email"]),
            "password": pwd_context.hash(user["pass_text"]),
            "phone_number": str(int(user["phone"])),
            "status": 1,
            "gender": "P"
            if user.get("gender") == "Perempuan" or user.get("gender") == "Female"
            else "L",
            "referral": user["refferal"]
            if user.get("refferal") != "0"
            else GenerateReferralCode(user["email"]),
            "saldo": int(user["saldo"]) if user.get("saldo") else 0,
            "role": 99,
            "address": user["address"],
        }
        result = await CreateOneData(db.users, user_data)
        if result.inserted_id:
            update_data = {"id_user": result.inserted_id, "gender": user_data["gender"]}
            res = await UpdateOneData(
                db.customers, {"service_number": service_number}, {"$set": update_data}
            )
            print(res)


async def MigrateManagementUser(db):
    user_list = await GetAggregateData(
        db.temp_users, [{"$match": {"role_id": {"$ne": "2"}}}]
    )
    for user in user_list:
        print(user)
        # service_number = int(user["no_services"])
        user_data = {
            "name": user["name"],
            "email": append_com_if_needed(user["email"]),
            "password": pwd_context.hash(user["pass_text"]),
            "phone_number": str(int(user["phone"])) if user.get("phone") else "81",
            "status": 1,
            "gender": "P"
            if user.get("gender") == "Perempuan" or user.get("gender") == "Female"
            else "L",
            "referral": user["refferal"]
            if user.get("refferal") != "0"
            else GenerateReferralCode(user["email"]),
            "saldo": int(user["saldo"]) if user.get("saldo") else 0,
            "address": user["address"],
        }
        if user["role_id"] == "1":
            user_data["role"] = UserRole.ADMIN.value
        elif user["role_id"] == "5":
            user_data["role"] = UserRole.SALES.value
        elif user["role_id"] == "6":
            user_data["role"] = UserRole.NETWORK_OPERATOR.value
        elif user["role_id"] == "7":
            user_data["role"] = UserRole.CUSTOMER_SERVICE.value
        elif user["role_id"] == "8":
            user_data["role"] = UserRole.ENGINEER.value

        result = await UpdateOneData(
            db.users, {"email": user_data["email"]}, {"$set": user_data}, upsert=True
        )
        # if result.inserted_id:
        #     update_data = {"id_user": result.inserted_id, "gender": user_data["gender"]}
        #     res = await UpdateOneData(
        #         db.customers, {"service_number": service_number}, {"$set": update_data}
        #     )
        #     print(res)


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
async def test(url: str):
    await SendTelegramImage(
        [url],
        5,
    )


@router.get("/migrate")
async def migrate_db(
    db_local: AsyncIOMotorClient = Depends(GetLocalhostDatabase),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    # result = await MigrateManagementUser(db)
    # result = await MigrateCustomerUser(db)
    # result = await MigrateCustomer(db)
    # phone = "08121830492"
    # return str(int(phone))
    collections = [
        "area_provinces",
        "area_regency",
        "area_subdistrict",
        "area_village",
        "configurations",
        "customers",
        "hardwares",
        "odc",
        "odp",
        "packages",
        "router",
        "users",
        "coverage_areas",
    ]
    for collection in collections:
        data = await GetAggregateData(db_local[collection])
        await CreateManyData(db[collection], data)

    return "sudah dimigrasi"
