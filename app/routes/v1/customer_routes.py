import asyncio
from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.models.customers import (
    CustomerInsertData,
    CustomerRegisterData,
    CustomerSortingsData,
    CustomerStatusData,
    CustomerUpdateData,
    CustomerProjections,
)
from app.models.notifications import NotificationTypeData
from app.models.generals import Pagination, SortingDirection
from app.models.tickets import TicketStatusData, TicketTypeData
from app.models.users import UserData, UserRole
from app.modules.geodistances import GetNearestODP
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetAggregateData,
    GetManyData,
    GetOneData,
    UpdateManyData,
    UpdateOneData,
)
from app.modules.mikrotik import ActivateMikrotikPPPSecret, DeleteMikrotikPPPSecret
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import (
    GenerateRandomString,
    GenerateReferralCode,
    GenerateUniqueCode,
    GetCurrentDateTime,
)
from app.modules.mpwa_whatsapp_message import SendMPWAWhatsappSingleMessage
from app.modules.telegram_message import SendTelegramNewCustomerMessage
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
)
from app.routes.v1.invoice_routes import CreateNewInvoice
from app.routes.v1.auth_routes import GetCurrentUser
from passlib.context import CryptContext
import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CUSTOMER_PASSWORD = os.getenv("DEFAULT_CUSTOMER_PASSWORD")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def UpdateRouterPostfix(db, id_router: str):
    try:
        exist_router = await GetOneData(db.router, {"_id": ObjectId(id_router)})
        if not exist_router:
            return

        prefix = exist_router.get("service_number_prefix")
        if not prefix:
            return

        result = await UpdateManyData(
            db.router,
            {"service_number_prefix": prefix},
            {"$inc": {"service_number_postfix": 1}},
        )
        return result
    except Exception:
        return


router = APIRouter(prefix="/customer", tags=["Customers"])


@router.get("")
async def get_customers(
    key: str = None,
    id_odp: str = None,
    id_router: str = None,
    status: int = None,
    referral: str = None,
    page: int = 1,
    items: int = 10,
    sort_key: CustomerSortingsData = CustomerSortingsData.SERVICE_NUMBER.value,
    sort_direction: SortingDirection = SortingDirection.ASC.value,
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
    if referral:
        query["referral"] = referral

    # add filter query
    pipeline.append({"$match": query})

    # add join id odp query
    pipeline.append(
        {
            "$lookup": {
                "from": "odp",
                "let": {"idOdp": "$id_odp"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idOdp"]}}},
                    {"$limit": 1},
                ],
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
                "let": {"idPackage": "$id_package"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idPackage"]}}},
                    {"$limit": 1},
                ],
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
                "let": {"idAddOnPackage": "$id_add_on_package"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$in": ["$_id", {"$ifNull": ["$$idAddOnPackage", []]}]
                            }
                        }
                    }
                ],
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

    pipeline.append({"$sort": {sort_key: 1 if sort_direction == "asc" else -1}})
    customer_data, count = await GetManyData(
        db.customers, pipeline, CustomerProjections, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}

    return JSONResponse(
        content={
            "customer_data": customer_data,
            "pagination_info": pagination_info,
        }
    )


@router.get("/billing-count")
async def get_customer_billing_count(
    key: str = None,
    id_odp: str = None,
    id_router: str = None,
    status: int = None,
    referral: str = None,
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
    else:
        query["status"] = {
            "$in": [CustomerStatusData.ACTIVE.value, CustomerStatusData.ISOLIR.value]
        }
    if referral:
        query["referral"] = referral

    # add filter query
    pipeline.append({"$match": query})

    # add join id package query
    pipeline.append(
        {
            "$lookup": {
                "from": "packages",
                "let": {"idPackage": "$id_package"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idPackage"]}}},
                    {"$limit": 1},
                ],
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
                "let": {"idAddOnPackage": "$id_add_on_package"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$in": ["$_id", {"$ifNull": ["$$idAddOnPackage", []]}]
                            }
                        }
                    }
                ],
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

    pipeline.append({"$group": {"_id": None, "count": {"$sum": "$billing"}}})
    billing_count = await GetAggregateData(db.customers, pipeline, {"count": 1})

    return JSONResponse(
        content={
            "billing_count": billing_count[0].get("count", 0)
            if len(billing_count) > 0
            else 0
        }
    )


@router.get("/maps")
async def get_customer_maps(
    key: str = None,
    id_odp: str = None,
    id_router: str = None,
    status: int = None,
    referral: str = None,
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
    if referral:
        query["referral"] = referral

    # add filter query
    pipeline.append({"$match": query})

    customer_maps_data = await GetAggregateData(
        db.customers, pipeline, CustomerProjections
    )
    return JSONResponse(content={"customer_maps_data": customer_maps_data})


@router.get("/generate-service-number")
async def generate_service_number(
    id_router: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_router = await GetOneData(db.router, {"_id": ObjectId(id_router)})
    if not exist_router:
        raise HTTPException(
            status_code=400,
            detail={"message": "Router Tidak Diketahui!"},
        )

    prefix = exist_router.get("service_number_prefix", 0)
    postfix = exist_router.get("service_number_postfix", 0)
    if not prefix:
        raise HTTPException(
            status_code=400,
            detail={"message": "Prefiks Router Tidak Diketahui!"},
        )

    digit_count = 7
    digit_postfix = digit_count - len(str(prefix))

    service_number = f"{prefix}{str(postfix).zfill(digit_postfix)}"
    return JSONResponse(
        content={
            "service_number": int(service_number),
            "pppoe_username": service_number,
            "pppoe_password": GenerateRandomString(str(service_number)),
        }
    )


@router.get("/stats")
async def get_customer_stats(
    referral: str = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )

    query = {}
    if referral:
        query["referral"] = referral
    pipeline = [
        {"$match": query},
        {
            "$group": {
                "_id": None,
                "nonactive": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", CustomerStatusData.NONACTIVE]},
                            1,
                            0,
                        ]
                    }
                },
                "active": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", CustomerStatusData.ACTIVE]}, 1, 0]
                    }
                },
                "pending": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", CustomerStatusData.PENDING]},
                            1,
                            0,
                        ]
                    }
                },
                "free": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", CustomerStatusData.FREE]}, 1, 0]
                    }
                },
                "isolir": {
                    "$sum": {
                        "$cond": [{"$eq": ["$status", CustomerStatusData.ISOLIR]}, 1, 0]
                    }
                },
                "paid_leave": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$status", CustomerStatusData.PAID_LEAVE]},
                            1,
                            0,
                        ]
                    }
                },
                "count": {"$sum": 1},
            }
        },
        {
            "$project": {
                "_id": 0,
                "nonactive": 1,
                "active": 1,
                "free": 1,
                "isolir": 1,
                "paid_leave": 1,
                "pending": 1,
                "count": 1,
            }
        },
    ]
    customer_stats_data = await GetAggregateData(db.customers, pipeline)
    return JSONResponse(
        content={
            "customer_stats_data": customer_stats_data[0]
            if len(customer_stats_data) > 0
            else {}
        }
    )


@router.get("/dashboard-info/{id}")
async def get_customer_dashboard_info(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    customer_invoice = {"amount": 0, "status": None}
    customer_package = {"name": None, "bandwidth": 0}
    month = str(GetCurrentDateTime().month).zfill(2)
    year = str(GetCurrentDateTime().year)
    exist_invoice = await GetOneData(
        db.invoices, {"id_customer": ObjectId(id), "month": month, "year": year}
    )
    if exist_invoice:
        customer_invoice["amount"] = exist_invoice.get("amount", 0)
        customer_invoice["status"] = exist_invoice.get("status", 0)

    exist_customer = await GetOneData(db.customers, {"_id": ObjectId(id)})
    if exist_customer:
        exist_package = await GetOneData(
            db.packages, {"_id": ObjectId(exist_customer.get("id_package"))}
        )
        if exist_package:
            customer_package["name"] = exist_package.get("name", None)
            customer_package["bandwidth"] = exist_package.get("bandwidth", 0)

    return JSONResponse(
        content={
            "customer_invoice": customer_invoice,
            "customer_package": customer_package,
        }
    )


@router.get("/detail/{id}")
async def get_customer_detail(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    pipeline = []
    query = {"_id": ObjectId(id)}
    # add filter query
    pipeline.append({"$match": query})

    # add join id odp query
    pipeline.append(
        {
            "$lookup": {
                "from": "odp",
                "let": {"idOdp": "$id_odp"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idOdp"]}}},
                    {"$limit": 1},
                ],
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
    # add join id router query
    pipeline.append(
        {
            "$lookup": {
                "from": "router",
                "let": {"idRouter": "$id_router"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idRouter"]}}},
                    {"$limit": 1},
                ],
                "as": "router",
            }
        }
    )
    pipeline.append(
        {
            "$addFields": {
                "router_name": {
                    "$ifNull": [{"$arrayElemAt": ["$router.name", 0]}, None]
                }
            }
        },
    )
    # add join id coverage area query
    pipeline.append(
        {
            "$lookup": {
                "from": "coverage_areas",
                "let": {"idCoverageArea": "$id_coverage_area"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idCoverageArea"]}}},
                    {"$limit": 1},
                ],
                "as": "coverage_area",
            }
        }
    )
    pipeline.append(
        {
            "$addFields": {
                "coverage_area_name": {
                    "$ifNull": [{"$arrayElemAt": ["$coverage_area.name", 0]}, None]
                }
            }
        },
    )

    # add join id package query
    pipeline.append(
        {
            "$lookup": {
                "from": "packages",
                "let": {"idPackage": "$id_package"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idPackage"]}}},
                    {"$limit": 1},
                ],
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
                "let": {"idAddOnPackage": "$id_add_on_package"},
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$in": ["$_id", {"$ifNull": ["$$idAddOnPackage", []]}]
                            }
                        }
                    }
                ],
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
    customer_data, _ = await GetManyData(
        db.customers, pipeline, {}, {"page": 1, "items": 1}
    )

    return JSONResponse(
        content={"customer_data": customer_data[0] if len(customer_data) > 0 else {}}
    )


@router.get("/check-data/{key}")
async def check_customer_data(
    key: int,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
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
            "registered_at": 1,
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


# @router.post("/register")
# async def register_customer(
#     data: CustomerRegisterData = Body(..., embed=True),
#     db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
# ):
#     try:
#         payload = data.dict(exclude_unset=True)
#         payload["unique_code"] = await GenerateUniqueCode(db)

#         # check exist id card number
#         exist_id_card_number = await GetOneData(
#             db.customers, {"id_card.number": payload["id_card"]["number"]}
#         )
#         if exist_id_card_number:
#             raise HTTPException(
#                 status_code=400,
#                 detail={"message": "Nomor Kartu Identitas Telah Digunakan!"},
#             )

#         # check exist email
#         exist_email = await GetOneData(db.users, {"email": payload["email"]})
#         if exist_email:
#             raise HTTPException(
#                 status_code=400,
#                 detail={"message": "Email Telah Digunakan!"},
#             )

#         # create user data
#         user_data = {
#             "name": payload["name"],
#             "email": payload["email"],
#             "password": pwd_context.hash(DEFAULT_CUSTOMER_PASSWORD),
#             "phone_number": payload["phone_number"],
#             "status": CustomerStatusData.NONACTIVE.value,
#             "gender": payload["gender"],
#             "saldo": 0,
#             "referral": GenerateReferralCode(payload["email"]),
#             "role": UserRole.CUSTOMER.value,
#             "address": payload["location"]["address"],
#         }
#         insert_user_result = await CreateOneData(db.users, user_data)
#         if not insert_user_result.inserted_id:
#             raise HTTPException(
#                 status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
#             )

#         # check package profile
#         package_data = await GetOneData(
#             db.packages, {"_id": ObjectId(payload["id_package"])}
#         )
#         if not package_data:
#             await DeleteOneData(db.users, {"_id": insert_user_result.inserted_id})
#             raise HTTPException(
#                 status_code=404, detail={"message": "Data Paket Tidak Ditemukan!"}
#             )

#         # formatting payload
#         payload["id_user"] = insert_user_result.inserted_id
#         payload["id_package"] = ObjectId(payload["id_package"])
#         payload["status"] = CustomerStatusData.PENDING.value
#         payload["registered_at"] = GetCurrentDateTime()
#         payload["created_at"] = GetCurrentDateTime()
#         odp = await GetNearestODP(
#             db,
#             longitude=payload.get("location", {}).get("longitude", 0),
#             latitude=payload.get("location", {}).get("latitude", 0),
#         )
#         if odp:
#             try:
#                 payload["id_odp"] = ObjectId(odp["_id"])
#             except Exception as e:
#                 print(str(e))
#                 pass

#         insert_customer_result = await CreateOneData(db.customers, payload)
#         if not insert_customer_result.inserted_id:
#             await DeleteOneData(db.users, {"email": user_data["email"]})
#             raise HTTPException(
#                 status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
#             )

#         ticket_data = {
#             "name": f"PSB-{int(GetCurrentDateTime().timestamp())}",
#             "status": TicketStatusData.PENDING,
#             "type": TicketTypeData.PSB.value,
#             "id_reporter": insert_user_result.inserted_id,
#             "id_assignee": None,
#             "title": "Pemasangan Baru",
#             "description": "Instalasi jaringan baru untuk Pelanggan",
#             "created_at": GetCurrentDateTime(),
#             "created_by": insert_user_result.inserted_id,
#         }
#         await CreateOneData(db.tickets, ticket_data)
#         asyncio.create_task(
#             SendTelegramNewCustomerMessage(db, str(insert_customer_result.inserted_id))
#         )
#         notification_data = {
#             "title": "Pemasangan Baru",
#             "description": "Instalasi jaringan baru untuk Pelanggan",
#             "type": NotificationTypeData.TICKET.value,
#             "is_read": 0,
#             "id_reporter": insert_user_result.inserted_id,
#             "created_at": GetCurrentDateTime(),
#         }
#         admin_user = await GetAggregateData(
#             db.users, [{"$match": {"role": UserRole.OWNER}}]
#         )
#         if len(admin_user) > 0:
#             for user in admin_user:
#                 notification_data["id_user"] = ObjectId(user["_id"])
#                 await CreateOneData(db.notifications, notification_data.copy())

#         return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})

#     except HTTPException as http_err:
#         raise http_err
#     except Exception as e:
#         print(str(e))
#         raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})
@router.post("/register")
async def register_customer(
    data: CustomerRegisterData = Body(..., embed=True),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        payload = data.dict(exclude_unset=True)
        payload["unique_code"] = await GenerateUniqueCode(db)

        exist_id_card_task = GetOneData(
            db.customers, {"id_card.number": payload["id_card"]["number"]}
        )
        exist_email_task = GetOneData(db.users, {"email": payload["email"]})
        exist_id_card, exist_email = await asyncio.gather(exist_id_card_task, exist_email_task)

        if exist_id_card:
            raise HTTPException(status_code=400, detail={"message": "Nomor Kartu Identitas Telah Digunakan!"})
        if exist_email:
            raise HTTPException(status_code=400, detail={"message": "Email Telah Digunakan!"})

        user_data = {
            "name": payload["name"],
            "email": payload["email"],
            "password": pwd_context.hash(DEFAULT_CUSTOMER_PASSWORD),
            "phone_number": payload["phone_number"],
            "status": CustomerStatusData.NONACTIVE.value,
            "gender": payload["gender"],
            "saldo": 0,
            "referral": GenerateReferralCode(payload["email"]),
            "role": UserRole.CUSTOMER.value,
            "address": payload["location"]["address"],
        }
        insert_user_result = await CreateOneData(db.users, user_data)
        if not insert_user_result.inserted_id:
            raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

        payload["id_user"] = insert_user_result.inserted_id
        payload["id_package"] = ObjectId(payload["id_package"])
        payload["status"] = CustomerStatusData.PENDING.value
        payload["registered_at"] = payload["created_at"] = GetCurrentDateTime()
        payload["service_number"] = f"AMR-{int(GetCurrentDateTime().timestamp())}"

        odp_task = GetNearestODP(
            db,
            longitude=payload.get("location", {}).get("longitude", 0),
            latitude=payload.get("location", {}).get("latitude", 0),
        )
        package_task = GetOneData(db.packages, {"_id": ObjectId(payload["id_package"])})
        odp, package_data = await asyncio.gather(odp_task, package_task)

        if not package_data:
            await DeleteOneData(db.users, {"_id": insert_user_result.inserted_id})
            raise HTTPException(status_code=404, detail={"message": "Data Paket Tidak Ditemukan!"})

        if odp:
            try:
                payload["id_odp"] = ObjectId(odp["_id"])
            except Exception:
                pass

        insert_customer_result = await CreateOneData(db.customers, payload)
        if not insert_customer_result.inserted_id:
            await DeleteOneData(db.users, {"_id": insert_user_result.inserted_id})
            raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

        asyncio.create_task(
            CreateOneData(db.tickets, {
                "name": f"PSB-{int(GetCurrentDateTime().timestamp())}",
                "status": TicketStatusData.PENDING,
                "type": TicketTypeData.PSB.value,
                "id_reporter": insert_user_result.inserted_id,
                "id_assignee": None,
                "title": "Pemasangan Baru",
                "description": "Instalasi jaringan baru untuk Pelanggan",
                "created_at": GetCurrentDateTime(),
                "created_by": insert_user_result.inserted_id,
            })
        )

        asyncio.create_task(
            SendTelegramNewCustomerMessage(db, str(insert_customer_result.inserted_id))
        )

        async def notify_admins():
            admin_users = await GetAggregateData(db.users, [{"$match": {"role": UserRole.OWNER}}])
            notification_data = {
                "title": "Pemasangan Baru",
                "description": "Instalasi jaringan baru untuk Pelanggan",
                "type": NotificationTypeData.TICKET.value,
                "is_read": 0,
                "id_reporter": insert_user_result.inserted_id,
                "created_at": GetCurrentDateTime(),
            }
            tasks = []
            for user in admin_users:
                notif = notification_data.copy()
                notif["id_user"] = ObjectId(user["_id"])
                tasks.append(CreateOneData(db.notifications, notif))
            if tasks:
                await asyncio.gather(*tasks)

        asyncio.create_task(notify_admins())

        return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.post("/add")
async def create_customer(
    data: CustomerInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    try:
        payload = data.dict(exclude_unset=True)
        # check exist service number
        exist_service_number = await GetOneData(
            db.customers, {"service_number": payload["service_number"]}
        )
        if exist_service_number:
            raise HTTPException(
                status_code=400, detail={"message": "Nomor layanan Telah Digunakan!"}
            )

        # check exist id card number
        exist_id_card_number = await GetOneData(
            db.customers, {"id_card.number": payload["id_card"]["number"]}
        )
        if exist_id_card_number:
            raise HTTPException(
                status_code=400,
                detail={"message": "Nomor Kartu Identitas Telah Digunakan!"},
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
            "password": pwd_context.hash(DEFAULT_CUSTOMER_PASSWORD),
            "phone_number": payload["phone_number"],
            "status": 0,
            "gender": payload["gender"],
            "referral": GenerateReferralCode(payload["email"]),
            "saldo": 0,
            "role": UserRole.CUSTOMER.value,
            "address": payload["location"]["address"],
        }
        if payload["status"] == CustomerStatusData.ACTIVE:
            user_data["status"] = 1

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

        # create id secret mikrotik
        disabled = (
            False
            if payload["status"] == CustomerStatusData.ACTIVE.value
            or payload["status"] == CustomerStatusData.FREE.value
            else True
        )
        is_secret_created = await ActivateMikrotikPPPSecret(db, payload, disabled)
        if not is_secret_created:
            await DeleteOneData(db.users, {"_id": insert_user_result.inserted_id})
            raise HTTPException(
                status_code=404, detail={"message": "Gagal Membuat Secret Mikrotik!"}
            )

        # formatting payload
        payload["id_user"] = insert_user_result.inserted_id
        if "id_add_on_package" in payload:
            payload["id_add_on_package"] = [
                ObjectId(item) for item in payload["id_add_on_package"]
            ]
        payload["id_router"] = ObjectId(payload["id_router"])
        payload["id_package"] = ObjectId(payload["id_package"])
        payload["id_coverage_area"] = ObjectId(payload["id_coverage_area"])
        payload["id_odp"] = ObjectId(payload["id_odp"])
        payload["registered_by"] = current_user.name
        payload["registered_at"] = GetCurrentDateTime()
        payload["unique_code"] = await GenerateUniqueCode(db)
        insert_customer_result = await CreateOneData(db.customers, payload)
        if not insert_customer_result:
            await DeleteOneData(db.users, {"email": user_data["email"]})
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        await UpdateRouterPostfix(db, str(payload["id_router"]))

        return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.put("/update/{id}")
async def update_customer(
    id: str,
    data: CustomerUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    try:
        payload = data.dict(exclude_unset=True)
        # check exist data
        exist_data = await GetOneData(db.customers, {"_id": ObjectId(id)})
        if not exist_data:
            raise HTTPException(
                status_code=404,
                detail={"message": NOT_FOUND_MESSAGE},
            )

        # check exist service number
        exist_service_number = await GetOneData(
            db.customers,
            {
                "service_number": payload["service_number"],
                "_id": {"$ne": ObjectId(id)},
            },
        )
        if exist_service_number:
            raise HTTPException(
                status_code=400, detail={"message": "Nomor layanan Telah Digunakan!"}
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

        # check exist email
        exist_email = await GetOneData(
            db.customers, {"email": payload["email"], "_id": {"$ne": ObjectId(id)}}
        )
        if exist_email:
            raise HTTPException(
                status_code=400,
                detail={"message": "Email Telah Digunakan!"},
            )

        # update mikrotik access
        disabled = (
            False
            if payload["status"] == CustomerStatusData.ACTIVE
            or payload["status"] == CustomerStatusData.FREE
            else True
        )
        await ActivateMikrotikPPPSecret(db, payload, disabled)

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
        if "unique_code" not in exist_data:
            payload["unique_code"] = await GenerateUniqueCode(db)

        update_result = await UpdateOneData(
            db.customers, {"_id": ObjectId(id)}, {"$set": payload}
        )
        if not update_result:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        if exist_data.get("service_number") != payload.get("service_number"):
            await UpdateRouterPostfix(db, str(payload["id_router"]))

        update_user = {}
        if "name" in payload:
            update_user.update({"name": payload["name"]})
        if "email" in payload:
            update_user.update({"email": payload["email"]})
        if "phone_number" in payload:
            update_user.update({"phone_number": payload["phone_number"]})
        if "gender" in payload:
            update_user.update({"gender": payload["gender"]})
        if "location" in payload and "address" in payload["location"]:
            update_user.update({"address": payload["location"]["address"]})
        if (
            payload["status"] == CustomerStatusData.ACTIVE
            or payload["status"] == CustomerStatusData.NONACTIVE
        ):
            update_user.update({"status": payload["status"]})

        await UpdateOneData(
            db.users, {"_id": ObjectId(exist_data["id_user"])}, {"$set": update_user}
        )
        return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.put("/update-status/{id}")
async def update_customer_status(
    id: str,
    status: CustomerStatusData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    try:
        exist_data = await GetOneData(db.customers, {"_id": ObjectId(id)})
        if not exist_data:
            raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

        if status == CustomerStatusData.NONACTIVE:
            await DeleteMikrotikPPPSecret(db, exist_data)
        else:
            disabled = (
                False
                if status == CustomerStatusData.ACTIVE
                or status == CustomerStatusData.FREE
                else True
            )
            await ActivateMikrotikPPPSecret(db, exist_data, disabled)

        result = await UpdateOneData(
            db.customers,
            {"_id": ObjectId(id)},
            {"$set": {"status": status}},
        )
        if not result:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        if (
            status == CustomerStatusData.ACTIVE
            or status == CustomerStatusData.NONACTIVE
        ):
            await UpdateOneData(
                db.users,
                {"_id": ObjectId(exist_data["id_user"])},
                {"$set": {"status": status}},
            )

        # create_invoice
        if (
            exist_data.get("billing_type") == "PRABAYAR"
            and exist_data.get("status") == CustomerStatusData.PENDING.value
            and status == CustomerStatusData.ACTIVE.value
        ):
            create_invoice_payload = {
                "id_customer": id,
                "month": str(GetCurrentDateTime().month).zfill(2),
                "year": str(GetCurrentDateTime().year),
            }
            await CreateNewInvoice(
                db, payload=create_invoice_payload, is_send_whatsapp=True
            )

        return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.put("/reject/{id}")
async def reject_customer(
    id: str,
    reason: str = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
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

        await DeleteMikrotikPPPSecret(db, exist_data)
        v_message = "*Pengajuan Pelanggan Ditolak* \n\n"
        v_message += f"Mohon maaf, Pengajuan pelanggan atas nama {exist_data.get('name')} ditolak dengan alasan {reason}"
        await SendMPWAWhatsappSingleMessage(exist_data.get("phone_number"), v_message)
        if "referral" in exist_data:
            referral_user = await GetOneData(
                db.users, {"referral": exist_data.get("referral")}
            )
            if referral_user:
                await SendMPWAWhatsappSingleMessage(
                    referral_user.get("phone_number"), v_message
                )

        return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.delete("/delete/{id}")
async def delete_customer(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
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

        await DeleteMikrotikPPPSecret(db, exist_data)

        return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})

    except HTTPException as http_err:
        raise http_err
    except Exception:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})
