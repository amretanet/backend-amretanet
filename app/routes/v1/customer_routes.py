from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.models.customers import (
    CustomerInsertData,
    CustomerRegisterData,
    CustomerStatusData,
)
from app.models.notifications import NotificationTypeData
from app.models.generals import Pagination
from app.models.tickets import TicketStatusData
from app.models.users import UserData
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.mikrotik import (
    CreateMikrotikPPPSecret,
    DeleteMikrotikPPPSecret,
    UpdateMikrotikPPPSecret,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import GetCurrentDateTime
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
)
from app.routes.v1.auth_routes import GetCurrentUser
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_PASSWORD = os.getenv("DEFAULT_PASSWORD")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


router = APIRouter(prefix="/customer", tags=["Customers"])


@router.get("")
async def get_customers(
    key: str = None,
    id_odp: str = None,
    id_router: str = None,
    status: int = None,
    is_maps_only: bool = False,
    page: int = 1,
    items: int = 1,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    pipeline = []
    query = {}
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
            {
                "$expr": {
                    "$regexMatch": {
                        "input": {"$toString": "$service_number"},
                        "regex": key,
                        "options": "i",
                    }
                }
            },
        ]
    if id_odp:
        query["id_odp"] = ObjectId(id_odp)
    if id_router:
        query["id_router"] = ObjectId(id_router)
    if status is not None:
        query["status"] = status

    # add filter query
    pipeline.append({"$match": query})

    # add join id odp query
    pipeline.append(
        {
            "$lookup": {
                "from": "odp",
                "localField": "id_odp",
                "foreignField": "_id",
                "pipeline": [{"$limit": 1}],
                "as": "odp",
            }
        }
    )
    pipeline.append(
        {
            "$addFields": {
                "odp_name": {"$ifNull": [{"$arrayElemAt": ["$odp.name", 0]}, None]}
            }
        },
    )

    # add join id package query
    pipeline.append(
        {
            "$lookup": {
                "from": "packages",
                "localField": "id_package",
                "foreignField": "_id",
                "pipeline": [{"$limit": 1}],
                "as": "package",
            }
        }
    )
    pipeline.append(
        {
            "$addFields": {
                "package_billing": {
                    "$ifNull": [{"$arrayElemAt": ["$package.price.regular", 0]}, 0]
                }
            }
        }
    )

    # add join id add-on package query
    pipeline.append(
        {
            "$lookup": {
                "from": "packages",
                "localField": "id_add_on_package",
                "foreignField": "_id",
                "pipeline": [],
                "as": "add_on_packages",
            }
        }
    )
    pipeline.append(
        {
            "$addFields": {
                "add_on_billing": {
                    "$sum": {
                        "$map": {
                            "input": "$add_on_packages",
                            "as": "add_on",
                            "in": {"$ifNull": ["$$add_on.price.regular", 0]},
                        }
                    }
                }
            }
        }
    )

    # counting package & add-on package price query
    pipeline.append(
        {
            "$addFields": {
                "billing": {"$add": ["$package_billing", "$add_on_billing"]}
            },
        }
    )

    # add projection query
    pipeline.append(
        {
            "$project": {
                "name": 1,
                "service_number": 1,
                "created_at": 1,
                "odp_name": 1,
                "phone_number": 1,
                "status": 1,
                "ppn": 1,
                "due_date": 1,
                "billing": 1,
                "referal": 1,
            }
        }
    )

    customer_maps_data, _ = await GetManyData(
        db.customers,
        [],
        {"_id": 0, "lat": "$location.latitude", "lng": "$location.longitude"},
    )
    if is_maps_only:
        return JSONResponse(content={"customer_maps_data": customer_maps_data})

    customer_data, count = await GetManyData(
        db.customers, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}

    return JSONResponse(
        content={
            "customer_data": customer_data,
            "customer_maps_data": customer_maps_data,
            "pagination_info": pagination_info,
        }
    )


@router.get("/detail/{id}")
async def get_customer_detail(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    customer_data = await GetOneData(db.customers, {"_id": ObjectId(id)})
    if not customer_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    return JSONResponse(content={"customer_data": customer_data})


@router.get("/check-data/{key}")
async def check_customer_data(
    key: int, db: AsyncIOMotorClient = Depends(GetAmretaDatabase)
):
    service_number = key
    phone_number = str(key)
    customer_data = await GetOneData(
        db.customers,
        {"$or": [{"service_number": service_number}, {"phone_number": phone_number}]},
        {
            "_id": 0,
            "name": 1,
            "service_number": 1,
            "phone_number": 1,
            "email": 1,
            "gender": 1,
            "due_date": 1,
            "created_at": 1,
        },
    )
    if not customer_data:
        raise HTTPException(status_code=404, detail={"messagge": NOT_FOUND_MESSAGE})

    current_month = GetCurrentDateTime().strftime("%m")
    current_year = GetCurrentDateTime().strftime("%Y")
    invoice_data = await GetOneData(
        db.invoices,
        {
            "service_number": customer_data["service_number"],
            "month": current_month,
            "year": current_year,
        },
        {"amount": 1, "status": 1, "due_date": 1},
    )
    if invoice_data:
        customer_data["invoice"] = invoice_data
    return JSONResponse(content={"customer_data": customer_data})


@router.post("/register")
async def register_customer(
    data: CustomerRegisterData = Body(..., embed=True),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        payload = data.dict(exclude_unset=True)
        payload["service_number"] = 2900000
        lates_service_number = await GetOneData(
            db.customers,
            {"service_number": {"$exists": True}},
            sort_by="service_number",
            sort_direction=-1,
        )
        if lates_service_number:
            payload["service_number"] = int(lates_service_number["service_number"]) + 1

        # check exist id card number
        exist_id_card_number = await GetOneData(
            db.customers, {"id_card.number": payload["id_card"]["number"]}
        )
        if exist_id_card_number:
            raise HTTPException(
                status_code=400,
                detail={"message": "Nomor Kartu Identitas Telah Digunakan!"},
            )

        # check exist id card number
        exist_phone_number = await GetOneData(
            db.customers, {"phone_number": payload["phone_number"]}
        )
        if exist_phone_number:
            raise HTTPException(
                status_code=400,
                detail={"message": "Nomor Telepon/Whatsapp Telah Digunakan!"},
            )

        # check exist email
        exist_email = await GetOneData(db.users, {"email": payload["email"]})
        if exist_email:
            raise HTTPException(
                status_code=400,
                detail={"message": "Email Telah Digunakan!"},
            )

        # create user data
        user_data = {
            "name": payload["name"],
            "email": payload["email"],
            # "password": pwd_context.hash(DEFAULT_PASSWORD),
            "phone_number": payload["phone_number"],
            "status": CustomerStatusData.nonactive.value,
            "gender": payload["gender"],
            "saldo": 0,
            "role": 99,
            "address": payload["location"]["address"],
        }
        insert_user_result = await CreateOneData(db.users, user_data)
        if not insert_user_result.inserted_id:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        # check package profile
        package_data = await GetOneData(
            db.packages, {"_id": ObjectId(payload["id_package"])}
        )
        if not package_data:
            await DeleteOneData(db.users, {"_id": insert_user_result.inserted_id})
            raise HTTPException(
                status_code=404, detail={"message": "Data Paket Tidak Ditemukan!"}
            )

        # formatting payload
        payload["id_user"] = insert_user_result.inserted_id
        payload["id_package"] = ObjectId(payload["id_package"])
        payload["status"] = CustomerStatusData.pending.value
        payload["created_at"] = GetCurrentDateTime()
        insert_customer_result = await CreateOneData(db.customers, payload)
        if not insert_customer_result.inserted_id:
            await DeleteOneData(db.users, {"email": user_data["email"]})
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )
        ticket_data = {
            "name": f"PSB-{int(GetCurrentDateTime().timestamp())}",
            "status": TicketStatusData.OPEN,
            "id_reporter": insert_user_result.inserted_id,
            "id_assignee": None,
            "title": "Pemasangan Baru",
            "description": "Instalasi jaringan baru untuk Customer",
            "created_at": GetCurrentDateTime(),
            "created_by": insert_user_result.inserted_id,
        }
        await CreateOneData(db.tickets, ticket_data)
        notification_data = {
            "title": "Pemasangan Baru",
            "description": "Instalasi jaringan baru untuk Customer",
            "type": NotificationTypeData.TICKET.value,
            "is_read": 0,
            "id_reporter": insert_user_result.inserted_id,
            "created_at": GetCurrentDateTime(),
        }
        await CreateOneData(db.notifications, notification_data)

        return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.post("/add")
async def create_customer(
    data: CustomerInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        payload = data.dict(exclude_unset=True)
        payload["service_number"] = 2900000
        lates_service_number = await GetOneData(
            db.customers,
            {"service_number": {"$exists": True}},
            sort_by="service_number",
            sort_direction=-1,
        )
        if lates_service_number:
            payload["service_number"] = int(lates_service_number["service_number"]) + 1

        # check exist id card number
        exist_id_card_number = await GetOneData(
            db.customers, {"id_card.number": payload["id_card"]["number"]}
        )
        if exist_id_card_number:
            raise HTTPException(
                status_code=400,
                detail={"message": "Nomor Kartu Identitas Telah Digunakan!"},
            )

        # check exist id card number
        exist_phone_number = await GetOneData(
            db.customers, {"phone_number": payload["phone_number"]}
        )
        if exist_phone_number:
            raise HTTPException(
                status_code=400,
                detail={"message": "Nomor Telepon/Whatsapp Telah Digunakan!"},
            )

        # check exist email
        exist_email = await GetOneData(db.users, {"email": payload["email"]})
        if exist_email:
            raise HTTPException(
                status_code=400,
                detail={"message": "Email Telah Digunakan!"},
            )

        # create user data
        user_data = {
            "name": payload["name"],
            "email": payload["email"],
            "password": pwd_context.hash(DEFAULT_PASSWORD),
            "phone_number": payload["phone_number"],
            "status": 1,
            "gender": payload["gender"],
            "saldo": 0,
            "role": 99,
            "address": payload["location"]["address"],
        }
        insert_user_result = await CreateOneData(db.users, user_data)
        if not insert_user_result.inserted_id:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

            # set service number

        # check package profile
        package_data = await GetOneData(
            db.packages, {"_id": ObjectId(payload["id_package"])}
        )
        if not package_data:
            await DeleteOneData(db.users, {"_id": insert_user_result.inserted_id})
            raise HTTPException(
                status_code=404, detail={"message": "Data Paket Tidak Ditemukan!"}
            )

        # create id secret mikrotik
        id_secret = await CreateMikrotikPPPSecret(
            db,
            payload["id_router"],
            payload["name"],
            package_data.get("router_profile", "default"),
            payload["service_number"],
        )
        if not id_secret:
            await DeleteOneData(db.users, {"_id": insert_user_result.inserted_id})
            raise HTTPException(
                status_code=404, detail={"message": "Gagal Membuat Secret Mikrotik!"}
            )

        # formatting payload
        payload["id_user"] = insert_user_result.inserted_id
        payload["id_secret"] = id_secret
        if "id_add_on_package" in payload:
            payload["id_add_on_package"] = [
                ObjectId(item) for item in payload["id_add_on_package"]
            ]
        payload["id_router"] = ObjectId(payload["id_router"])
        payload["id_package"] = ObjectId(payload["id_package"])
        payload["id_coverage_area"] = ObjectId(payload["id_coverage_area"])
        payload["id_odp"] = ObjectId(payload["id_odp"])
        payload["status"] = 1
        payload["created_by"] = current_user.name
        payload["created_at"] = GetCurrentDateTime()
        insert_customer_result = await CreateOneData(db.customers, payload)
        if not insert_customer_result:
            await DeleteOneData(db.users, {"email": user_data["email"]})
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.put("/update/{id}")
async def update_customer(
    id: str,
    data: CustomerInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        payload = data.dict(exclude_unset=True)
        # check exist data
        exist_data = await GetOneData(db.customers, {"_id": ObjectId(id)})
        if not exist_data:
            raise HTTPException(
                status_code=404,
                detail={"message": NOT_FOUND_MESSAGE},
            )

        # check exist id card number
        exist_id_card_number = await GetOneData(
            db.customers,
            {
                "id_card.number": payload["id_card"]["number"],
                "_id": {"$ne": ObjectId(id)},
            },
        )
        if exist_id_card_number:
            raise HTTPException(
                status_code=400,
                detail={"message": "Nomor Kartu Identitas Telah Digunakan!"},
            )

        # check exist id card number
        exist_phone_number = await GetOneData(
            db.customers,
            {"phone_number": payload["phone_number"], "_id": {"$ne": ObjectId(id)}},
        )
        if exist_phone_number:
            raise HTTPException(
                status_code=400,
                detail={"message": "Nomor Telepon/Whatsapp Telah Digunakan!"},
            )

        # check exist email
        exist_email = await GetOneData(
            db.customers, {"email": payload["email"], "_id": {"$ne": ObjectId(id)}}
        )
        if exist_email:
            raise HTTPException(
                status_code=400,
                detail={"message": "Email Telah Digunakan!"},
            )

        # check package profile
        package_data = await GetOneData(
            db.packages, {"_id": ObjectId(payload["id_package"])}
        )
        if not package_data:
            raise HTTPException(
                status_code=404, detail={"message": "Data Paket Tidak Ditemukan!"}
            )

        # update secret mikrotik
        if "id_secret" in exist_data:
            disabled = True if exist_data["status"] in [0, 4, 5] else False
            is_secret_updated = await UpdateMikrotikPPPSecret(
                db,
                exist_data.get("id_secret", ""),
                payload["id_router"],
                payload["name"],
                package_data.get("router_profile", "default"),
                exist_data.get("service_number"),
                disabled=disabled,
            )
            if not is_secret_updated:
                id_secret = await CreateMikrotikPPPSecret(
                    db,
                    payload["id_router"],
                    payload["name"],
                    package_data.get("router_profile", "default"),
                    exist_data.get("service_number"),
                )
                payload["id_secret"] = id_secret
        else:
            id_secret = await CreateMikrotikPPPSecret(
                db,
                payload["id_router"],
                payload["name"],
                package_data.get("router_profile", "default"),
                exist_data.get("service_number"),
            )
            payload["id_secret"] = id_secret

        # formatting payload
        if "id_add_on_package" in payload:
            payload["id_add_on_package"] = [
                ObjectId(item) for item in payload["id_add_on_package"]
            ]
        payload["id_router"] = ObjectId(payload["id_router"])
        payload["id_package"] = ObjectId(payload["id_package"])
        payload["id_coverage_area"] = ObjectId(payload["id_coverage_area"])
        payload["id_odp"] = ObjectId(payload["id_odp"])
        payload["updated_by"] = current_user.name
        payload["updated_at"] = GetCurrentDateTime()

        if exist_data["status"] == CustomerStatusData.pending:
            payload["status"] = CustomerStatusData.active
            await UpdateOneData(
                db.users,
                {"_id": ObjectId(exist_data["id_user"])},
                {"$set": {"status": CustomerStatusData.active}},
            )

        update_result = await UpdateOneData(
            db.customers, {"_id": ObjectId(id)}, {"$set": payload}
        )
        if not update_result:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.put("/update-status/{id}")
async def update_customer_status(
    id: str,
    status: CustomerStatusData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        exist_data = await GetOneData(db.customers, {"_id": ObjectId(id)})
        if not exist_data:
            raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

        # check package profile
        package_data = await GetOneData(
            db.packages, {"_id": ObjectId(exist_data["id_package"])}
        )
        if not package_data:
            raise HTTPException(
                status_code=404, detail={"message": "Data Paket Tidak Ditemukan!"}
            )

        if status == CustomerStatusData.nonactive:
            await DeleteMikrotikPPPSecret(
                db, exist_data["id_router"], exist_data["id_secret"]
            )
            await UpdateOneData(
                db.customers,
                {"_id": ObjectId(id)},
                {"$set": {"status": status}, "$unset": {"id_secret": ""}},
            )
        else:
            disabled = (
                True
                if status == CustomerStatusData.isolir
                or status == CustomerStatusData.paid
                else False
            )
            if "id_secret" in exist_data:
                await UpdateMikrotikPPPSecret(
                    db,
                    exist_data.get("id_secret", ""),
                    exist_data["id_router"],
                    exist_data["name"],
                    package_data.get("router_profile", "default"),
                    exist_data["service_number"],
                    disabled=disabled,
                )
                await UpdateOneData(
                    db.customers,
                    {"_id": ObjectId(id)},
                    {"$set": {"status": status}},
                )
            else:
                id_secret = await CreateMikrotikPPPSecret(
                    db,
                    exist_data["id_router"],
                    exist_data["name"],
                    package_data.get("router_profile", "default"),
                    exist_data["service_number"],
                )
                if not id_secret:
                    raise HTTPException(
                        status_code=404,
                        detail={"message": "Gagal Membuat Secret Mikrotik!"},
                    )

                await UpdateOneData(
                    db.customers,
                    {"_id": ObjectId(id)},
                    {"$set": {"status": status, "id_secret": id_secret}},
                )

        return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.delete("/delete/{id}")
async def delete_customer(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        exist_data = await GetOneData(db.customers, {"_id": ObjectId(id)})
        if not exist_data:
            raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

        result = await DeleteOneData(db.customers, {"_id": ObjectId(id)})
        if not result.deleted_count:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        if "id_user" in exist_data:
            await DeleteOneData(db.users, {"_id": ObjectId(exist_data["id_user"])})

        if "id_secret" in exist_data and "id_router" in exist_data:
            await DeleteMikrotikPPPSecret(
                db, exist_data["id_router"], exist_data["id_secret"]
            )

        return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})
