from fastapi import (
    APIRouter,
    Depends,
)
from fastapi.responses import JSONResponse
from app.models.options import (
    ProvinceOptionProjections,
    RegencyOptionProjections,
    SubdistrictOptionProjections,
    VillageOptionProjections,
)
from app.modules.generals import AddURLHTTPProtocol
from app.models.users import UserData
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import GetDataCount, GetManyData, GetOneData
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
import requests
import os
from urllib.parse import urljoin
from requests.auth import HTTPBasicAuth

router = APIRouter(prefix="/options", tags=["Options"])


@router.get("/user")
async def get_user_options(
    role: int = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if role:
        query["role"] = role

    pipeline = [{"$match": query}, {"$sort": {"role": 1, "name": -1}}]

    user_options, _ = await GetManyData(
        db.users, pipeline, {"_id": 0, "title": "$name", "value": "$_id", "role": 1}
    )
    return JSONResponse(content={"user_options": user_options})


@router.get("/ticket-title")
async def get_ticket_title_options(
    current_user: UserData = Depends(GetCurrentUser),
):
    ticket_title_options = [
        "Gangguan Pada Jaringan",
        "Pemasangan Baru",
        "Jaringan Unspect",
        "Pindah Alamat",
        "Pergantian Alat",
        "Jemput Pembayaran",
        "Konfirmasi Layanan",
        "Berhenti Berlangganan",
        "Cek Coverage Area",
        "Pendaftaran Refferal",
        "Top up /Transfer Saldo",
        "Pembangunan Baru",
        "Migrasi ODC",
        "Migrasi ODP",
        "Cek ODC",
        "Cek ODP",
        "Perbaikan ODC",
        "Perbaikan ODP",
    ]

    return JSONResponse(content={"ticket_title_options": ticket_title_options})


@router.get("/coverage-area")
async def get_coverage_area_options(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    CoverageAreaOptionProjections = {"_id": 0, "title": "$name", "value": "$_id"}
    coverage_area_options, _ = await GetManyData(
        db.coverage_areas, [], CoverageAreaOptionProjections
    )
    return JSONResponse(content={"coverage_area_options": coverage_area_options})


@router.get("/odc")
async def get_odc_options(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    ODCOptionProjections = {"_id": 0, "title": "$name", "value": "$_id"}
    odc_options, _ = await GetManyData(db.odc, [], ODCOptionProjections)
    return JSONResponse(content={"odc_options": odc_options})


@router.get("/odp")
async def get_odp_options(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    ODPOptionProjections = {"_id": 0, "title": "$name", "value": "$_id"}
    odp_options, _ = await GetManyData(db.odp, [], ODPOptionProjections)
    return JSONResponse(content={"odp_options": odp_options})


@router.get("/router")
async def get_router_options(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    RouterOptionProjections = {"_id": 0, "title": "$name", "value": "$_id"}
    router_options, _ = await GetManyData(db.router, [], RouterOptionProjections)
    return JSONResponse(content={"router_options": router_options})


@router.get("/package")
async def get_package_options(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    PackageOptionProjections = {
        "_id": 0,
        "title": "$name",
        "value": "$_id",
        "category": 1,
        "price": 1,
        "router_profile": 1,
        "bandwidth": 1,
    }
    package_options, _ = await GetManyData(db.packages, [], PackageOptionProjections)
    return JSONResponse(content={"package_options": package_options})


@router.get("/router-profile")
async def get_router_profile_options(
    name: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    router_profile_options = []

    exist_router = await GetOneData(db.router, {"name": name})
    if not exist_router:
        return JSONResponse(content={"router_profile_options": router_profile_options})

    host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
    url = urljoin(host, "/rest/ppp/profile")
    username = exist_router.get("username", "")
    password = exist_router.get("password", "")
    try:
        response = requests.get(url, auth=HTTPBasicAuth(username, password))

        if response.status_code == 200:
            temp_profile = response.json()
            router_profile_options = [
                {"title": item.get("name", ""), "value": item.get("name", "")}
                for item in temp_profile
            ]
        else:
            router_profile_options = []
    except requests.exceptions.RequestException as e:
        router_profile_options = []

    return JSONResponse(content={"router_profile_options": router_profile_options})


@router.get("/area-province")
async def get_province_options(
    key: str = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if key:
        query["name"] = {"$regex": key, "$options": "i"}

    pipeline = [{"$match": query}]

    province_data, _ = await GetManyData(
        db.area_provinces, pipeline, ProvinceOptionProjections
    )
    return JSONResponse(content={"province_data": province_data})


@router.get("/area-regency")
async def get_regency_options(
    province: str,
    key: str = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {"province": province}
    if key:
        query["name"] = {"$regex": key, "$options": "i"}

    pipeline = [{"$match": query}]

    regency_data, _ = await GetManyData(
        db.area_regency, pipeline, RegencyOptionProjections
    )
    return JSONResponse(content={"regency_data": regency_data})


@router.get("/area-subdistrict")
async def get_subdistrict_options(
    regency: str,
    key: str = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {"regency": regency}
    if key:
        query["name"] = {"$regex": key, "$options": "i"}

    pipeline = [{"$match": query}]

    subdistrict_data, _ = await GetManyData(
        db.area_subdistrict, pipeline, SubdistrictOptionProjections
    )
    return JSONResponse(content={"subdistrict_data": subdistrict_data})


@router.get("/area-village")
async def get_village_options(
    subdistrict: str,
    key: str = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {"subdistrict": subdistrict}
    if key:
        query["name"] = {"$regex": key, "$options": "i"}

    pipeline = [{"$match": query}]

    village_data, _ = await GetManyData(
        db.area_village, pipeline, VillageOptionProjections
    )
    return JSONResponse(content={"village_data": village_data})


@router.get("/whatsapp-contact")
async def get_whatsapp_contact_options(
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    contact_count = await GetDataCount(db.users)
    all_contact_data = [
        {
            "title": "Semua Kontak",
            "count": contact_count,
            "group": "user",
            "value": "all",
        }
    ]
    # by user
    pipeline = [
        {
            "$group": {
                "_id": "$role",
                "count": {"$sum": 1},
            }
        },
    ]
    user_data, _ = await GetManyData(db.users, pipeline)
    user_data = [
        {
            "title": str(item["_id"]),
            "count": item["count"],
            "group": "user",
            "value": str(item["_id"]),
        }
        for item in user_data
    ]
    # by package
    pipeline = [
        {
            "$group": {
                "_id": "$id_package",
                "count": {"$sum": 1},
            }
        },
        {
            "$lookup": {
                "from": "packages",
                "localField": "_id",
                "foreignField": "_id",
                "as": "package",
            }
        },
        {"$unwind": "$package"},
    ]
    package_data, _ = await GetManyData(db.customers, pipeline)
    package_data = [
        {
            "title": item.get("package", "").get("name", "-"),
            "count": item.get("count", 0),
            "group": "package",
            "value": item["_id"],
        }
        for item in package_data
    ]
    # by coverage area
    pipeline = [
        {
            "$group": {
                "_id": "$id_coverage_area",
                "count": {"$sum": 1},
            }
        },
        {
            "$lookup": {
                "from": "coverage_areas",
                "localField": "_id",
                "foreignField": "_id",
                "as": "coverage_area",
            }
        },
        {"$unwind": "$coverage_area"},
    ]
    coverage_area_data, _ = await GetManyData(db.customers, pipeline)
    coverage_area_data = [
        {
            "title": item.get("coverage_area", "").get("name", "-"),
            "count": item.get("count", 0),
            "group": "coverage_area",
            "value": item["_id"],
        }
        for item in coverage_area_data
    ]
    # by odp
    pipeline = [
        {
            "$group": {
                "_id": "$id_odp",
                "count": {"$sum": 1},
            }
        },
        {
            "$lookup": {
                "from": "odp",
                "localField": "_id",
                "foreignField": "_id",
                "as": "odp",
            }
        },
        {"$unwind": "$odp"},
    ]
    odp_data, _ = await GetManyData(db.customers, pipeline)
    odp_data = [
        {
            "title": item.get("odp", "").get("name", "-"),
            "count": item.get("count", 0),
            "group": "odp",
            "value": item["_id"],
        }
        for item in odp_data
    ]

    contact_options = (
        all_contact_data + user_data + package_data + coverage_area_data + odp_data
    )
    return JSONResponse(content={"contact_options": contact_options})
