import base64
from calendar import monthrange
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from typing import Optional, List
import asyncio
from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from app.models.invoices import (
    InvoiceInsertData,
    InvoiceOwnerVerifiedStatusData,
    InvoiceSortingsData,
    InvoiceStatusData,
    InvoiceUpdateData,
)
from app.models.payments import PaymentMethodData
from app.models.generals import Pagination, SortingDirection
from app.models.users import UserData, UserRole
from app.modules.crud_operations import (
    CreateOneData,
    DeleteManyData,
    DeleteOneData,
    GetAggregateData,
    GetDistinctData,
    GetManyData,
    GetOneData,
    UpdateManyData,
    UpdateOneData,
)
from app.modules.pdf import CreateInvoicePDF, CreateInvoiceThermal
from app.modules.mikrotik import ActivateMikrotikPPPSecret
from app.modules.telegram_message import SendTelegramPaymentMessage
from app.modules.whatsapp_message import (
    SendWhatsappCustomerActivatedMessage,
    SendWhatsappIsolirMessage,
    SendWhatsappPaymentCreatedMessage,
    SendWhatsappPaymentOverdueMessage,
    SendWhatsappPaymentReminderMessage,
    SendWhatsappPaymentSuccessMessage,
)
from app.models.customers import CustomerStatusData
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import GetCurrentDateTime, GetDueDateRange, RemoveFilePath
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    EXIST_DATA_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
)
from app.routes.v1.auth_routes import GetCurrentUser
from app.routes.v1.payment_routes import CheckMitraFee
import os
from dotenv import load_dotenv

load_dotenv()

PPN = int(os.getenv("PPN"))
PAID_LEAVE_PERCENTAGE = int(os.getenv("PAID_LEAVE_PERCENTAGE"))


router = APIRouter(prefix="/invoice", tags=["Invoice"])


@router.get("")
async def get_invoice(
    id_customer: str = None,
    key: str = None,
    month: str = None,
    year: str = None,
    status: str = None,
    owner_verified_status: InvoiceOwnerVerifiedStatusData = None,
    page: int = 1,
    items: int = 1,
    sort_key: InvoiceSortingsData = InvoiceSortingsData.DUE_DATE.value,
    sort_direction: SortingDirection = SortingDirection.ASC.value,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if id_customer:
        query["id_customer"] = ObjectId(id_customer)

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
    if status:
        query["status"] = status
    if month:
        query["month"] = month
    if year:
        query["year"] = year
    if owner_verified_status is not None:
        query["owner_verified_status"] = owner_verified_status

    pipeline = [
        {"$match": query},
        {
            "$lookup": {
                "from": "customers",
                "let": {"idCustomer": "$id_customer"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idCustomer"]}}},
                    {
                        "$project": {
                            "status": 1,
                            "id_package": 1,
                            "id_add_on_package": 1,
                        }
                    },
                ],
                "as": "customer",
            }
        },
        {"$unwind": "$customer"},
        {"$sort": {sort_key: 1 if sort_direction == "asc" else -1}},
    ]

    invoice_data, count = await GetManyData(
        db.invoices, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "invoice_data": invoice_data,
            "pagination_info": pagination_info,
        }
    )


@router.get("/detail/{id}")
async def get_invoice_detail(
    id: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    invoice_data = await GetOneData(
        db.invoices,
        {"_id": ObjectId(id)},
        {
            "name": 1,
            "service_number": 1,
            "due_date": 1,
            "status": 1,
            "amount": 1,
        },
    )
    if not invoice_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    return JSONResponse(content={"invoice_data": invoice_data})


@router.get("/generate")
async def generate_invoice(
    is_send_whatsapp: bool = False,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    pipeline = []
    max_date_of_month = monthrange(
        GetCurrentDateTime().year, GetCurrentDateTime().month
    )[1]
    current_month_dates, next_month_dates = GetDueDateRange(10)
    query = {
        "status": {
            "$in": [
                CustomerStatusData.ACTIVE.value,
                CustomerStatusData.PAID_LEAVE.value,
            ]
        },
        "$or": [
            {
                "due_date": {"$in": current_month_dates},
            },
            {
                "due_date": {"$in": next_month_dates},
            },
        ],
    }

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
                    {
                        "$project": {
                            "name": 1,
                            "price": 1,
                        }
                    },
                    {"$limit": 1},
                ],
                "as": "package",
            }
        }
    )
    pipeline.append(
        {
            "$addFields": {
                "package_amount": {
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
                    },
                    {
                        "$project": {
                            "name": 1,
                            "price": 1,
                        }
                    },
                ],
                "as": "add_on_packages",
            }
        }
    )
    pipeline.append(
        {
            "$addFields": {
                "add_on_package_amount": {
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
                "amount": {"$add": ["$package_amount", "$add_on_package_amount"]}
            },
        }
    )

    # add projection query
    pipeline.append(
        {
            "$project": {
                "name": 1,
                "service_number": 1,
                "due_date": 1,
                "ppn": 1,
                "package": 1,
                "package_amount": 1,
                "add_on_packages": 1,
                "add_on_package_amount": 1,
                "amount": 1,
                "status": 1,
                "unique_code": 1,
            }
        }
    )

    customer_data = await GetAggregateData(db.customers, pipeline)
    if len(customer_data) == 0:
        return

    invoice_ids = []
    invoice_exist = 0
    invoice_created = 0
    current_date = GetCurrentDateTime()
    next_month = current_date + relativedelta(months=1)
    for customer in customer_data:
        try:
            customer_due_date = customer.get("due_date")
            if int(customer_due_date) > max_date_of_month:
                customer_due_date = str(max_date_of_month).zfill(2)
            target_month = current_date.strftime("%m")
            target_year = current_date.strftime("%Y")
            if customer_due_date in next_month_dates:
                target_month = next_month.strftime("%m")
                target_year = next_month.strftime("%Y")

            query = {
                "service_number": customer["service_number"],
                "month": target_month,
                "year": target_year,
            }
            exist_invoice = await GetOneData(db.invoices, query)
            if exist_invoice:
                invoice_exist += 1
                continue

            unique_code = customer.get("unique_code", 1)
            ppn = 0
            paid_leave_discount = 0
            if customer.get("ppn", 0):
                ppn = customer["amount"] * (PPN / 100)

            if customer["status"] == CustomerStatusData.PAID_LEAVE.value:
                paid_leave_discount = customer["amount"] * (
                    (100 - PAID_LEAVE_PERCENTAGE) / 100
                )
                customer["amount"] = customer["amount"] - paid_leave_discount

            final_amount = customer["amount"] + ppn + unique_code
            invoice_data = {
                "id_customer": ObjectId(customer["_id"]),
                "name": customer["name"],
                "service_number": customer["service_number"],
                "package": customer["package"],
                "due_date": datetime.strptime(
                    f"{target_year}-{target_month}-{customer_due_date} 23:59:59",
                    "%Y-%m-%d %H:%M:%S",
                ),
                "add_on_packages": customer["add_on_packages"],
                "month": target_month,
                "year": target_year,
                "status": "UNPAID",
                "package_amount": customer["package_amount"],
                "add_on_package_amount": customer["add_on_package_amount"],
                "ppn": ppn,
                "unique_code": unique_code,
                "amount": final_amount,
                "created_at": GetCurrentDateTime(),
            }
            if paid_leave_discount:
                invoice_data["paid_leave_discount"] = paid_leave_discount

            invoice_result = await CreateOneData(db.invoices, invoice_data)
            if not invoice_result.inserted_id:
                raise HTTPException(
                    status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
                )

            if is_send_whatsapp:
                invoice_ids.append(str(invoice_result.inserted_id))

            invoice_created += 1
        except Exception as e:
            print(str(e))
            continue

    if len(invoice_ids) > 0:
        asyncio.create_task(SendWhatsappPaymentCreatedMessage(db, invoice_ids))

    return JSONResponse(
        content={
            "invoice_exist": invoice_exist,
            "invoice_created": invoice_created,
        }
    )


@router.get("/pdf")
async def print_invoice_pdf(
    id: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    decoded_id = base64.b64decode(id).decode("utf-8")
    id_list = [ObjectId(item.strip()) for item in decoded_id.split(",")]
    pipeline = [
        {"$match": {"_id": {"$in": id_list}}},
        {
            "$lookup": {
                "from": "customers",
                "let": {"idCustomer": "$id_customer"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idCustomer"]}}},
                    {
                        "$project": {
                            "name": 1,
                            "email": 1,
                            "phone_number": 1,
                            "address": "$location.address",
                        },
                    },
                ],
                "as": "customer",
            }
        },
        {"$unwind": "$customer"},
    ]
    invoice_data = await GetAggregateData(db.invoices, pipeline)
    if len(invoice_data) == 0:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    pdf_bytes = CreateInvoicePDF(invoice_data)
    if len(invoice_data) == 1:
        file_name = f"INVOICE-{invoice_data[0].get('name', '')}-{GetCurrentDateTime().timestamp()}.pdf"
    else:
        file_name = f"INVOICE-PELANGGAN-{GetCurrentDateTime().timestamp()}.pdf"
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


@router.get("/thermal")
async def print_invoice_thermal(
    id: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    decoded_id = base64.b64decode(id).decode("utf-8")
    id_list = [ObjectId(item.strip()) for item in decoded_id.split(",")]
    pipeline = [
        {"$match": {"_id": {"$in": id_list}}},
        {
            "$lookup": {
                "from": "customers",
                "let": {"idCustomer": "$id_customer"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idCustomer"]}}},
                    {
                        "$project": {
                            "name": 1,
                            "email": 1,
                            "phone_number": 1,
                            "address": "$location.address",
                        },
                    },
                ],
                "as": "customer",
            }
        },
        {"$unwind": "$customer"},
    ]
    invoice_data = await GetAggregateData(db.invoices, pipeline)
    if len(invoice_data) == 0:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    pdf_bytes = CreateInvoiceThermal(invoice_data)
    if len(invoice_data) == 1:
        file_name = f"INVOICE-{invoice_data[0].get('name', '')}-{GetCurrentDateTime().timestamp()}.pdf"
    else:
        file_name = f"INVOICE-PELANGGAN-{GetCurrentDateTime().timestamp()}.pdf"
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


@router.get("/created")
async def invoice_whatsapp_created(
    id: str = None,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    invoice_ids = []
    if id:
        decoded_id = base64.b64decode(id).decode("utf-8")
        invoice_ids = [item.strip() for item in decoded_id.split(",")]
    else:
        from_date = GetCurrentDateTime().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        to_date = (GetCurrentDateTime() + timedelta(days=4)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )
        invoice_ids = await GetDistinctData(
            db.invoices,
            {
                "status": InvoiceStatusData.UNPAID.value,
                "due_date": {"$gte": from_date, "$lte": to_date},
                "is_whatsapp_sended": {"$exists": False},
            },
            "_id",
        )

    if len(invoice_ids) > 0:
        asyncio.create_task(SendWhatsappPaymentCreatedMessage(db, invoice_ids))

    return JSONResponse(content={"message": "Pengingat Telah Dikirimkan!"})


@router.get("/whatsapp-reminder")
async def invoice_whatsapp_reminder(
    id: str = None,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    invoice_ids = []
    if id:
        decoded_id = base64.b64decode(id).decode("utf-8")
        invoice_ids = [item.strip() for item in decoded_id.split(",")]
    else:
        from_date = GetCurrentDateTime().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        to_date = GetCurrentDateTime().replace(
            hour=23, minute=59, second=59, microsecond=0
        )

        invoice_ids = await GetDistinctData(
            db.invoices,
            {
                "status": InvoiceStatusData.UNPAID.value,
                "due_date": {"$gte": from_date, "$lte": to_date},
                "is_whatsapp_reminder_sended": {"$exists": False},
            },
            "_id",
        )

    if len(invoice_ids) > 0:
        asyncio.create_task(SendWhatsappPaymentReminderMessage(db, invoice_ids))

    return JSONResponse(content={"message": "Pengingat Telah Dikirimkan!"})


@router.get("/overdue")
async def invoice_whatsapp_overdue(
    id: str = None,
    is_delay: bool = False,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    invoice_ids = []
    if id:
        decoded_id = base64.b64decode(id).decode("utf-8")
        invoice_ids = [item.strip() for item in decoded_id.split(",")]
    else:
        invoice_ids = await GetDistinctData(
            db.invoices,
            {
                "status": InvoiceStatusData.UNPAID.value,
                "due_date": {"$lt": GetCurrentDateTime()},
                "is_whatsapp_overdue_sended": {"$exists": False},
            },
            "_id",
        )

    if len(invoice_ids) > 0:
        asyncio.create_task(SendWhatsappPaymentOverdueMessage(db, invoice_ids))

    return JSONResponse(content={"message": "Pesan Telah Dikirimkan!"})


@router.get("/isolir-customer")
async def isolir_customer(
    id: str = None,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    invoice_ids = []
    if id:
        decoded_id = base64.b64decode(id).decode("utf-8")
        invoice_ids = [item.strip() for item in decoded_id.split(",")]
        for id in invoice_ids:
            invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id)})
            if not invoice_data:
                continue

            customer_data = await GetOneData(
                db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
            )
            if not customer_data:
                continue

            await UpdateOneData(
                db.customers,
                {"_id": ObjectId(invoice_data["id_customer"])},
                {"$set": {"status": CustomerStatusData.ISOLIR.value}},
            )
            await ActivateMikrotikPPPSecret(db, customer_data, True)
    else:
        pipeline = [
            {
                "$match": {
                    "status": InvoiceStatusData.UNPAID.value,
                    "due_date": {"$lt": GetCurrentDateTime()},
                    "is_whatsapp_isolir_sended": {"$exists": False},
                }
            }
        ]
        invoice_data = await GetAggregateData(db.invoices, pipeline)
        for invoice in invoice_data:
            customer_data = await GetOneData(
                db.customers, {"_id": ObjectId(invoice["id_customer"])}
            )
            if not customer_data:
                continue

            if customer_data.get("status") != CustomerStatusData.ISOLIR.value:
                await UpdateOneData(
                    db.customers,
                    {"_id": ObjectId(invoice["id_customer"])},
                    {"$set": {"status": CustomerStatusData.ISOLIR.value}},
                )
                await ActivateMikrotikPPPSecret(db, customer_data, True)
                invoice_ids.append(invoice["_id"])

    if len(invoice_ids) > 0:
        asyncio.create_task(SendWhatsappIsolirMessage(db, invoice_ids))

    return JSONResponse(content={"message": "Pengguna Telah Diisolir!"})


@router.get("/activate-customer")
async def activate_customer(
    id: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    decoded_id = base64.b64decode(id).decode("utf-8")
    id_list = [item.strip() for item in decoded_id.split(",")]
    for id in id_list:
        invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id)})
        if not invoice_data:
            continue

        customer_data = await GetOneData(
            db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
        )
        if not customer_data:
            continue

        await UpdateOneData(
            db.customers,
            {"_id": ObjectId(invoice_data["id_customer"])},
            {"$set": {"status": CustomerStatusData.ACTIVE.value}},
        )
        await ActivateMikrotikPPPSecret(db, customer_data, False)
        asyncio.create_task(
            SendWhatsappCustomerActivatedMessage(db, invoice_data["id_customer"])
        )

    return JSONResponse(content={"message": "Pengguna Telah Diaktifkan!"})


@router.post("/add")
async def create_invoice(
    data: InvoiceInsertData = Body(..., embed=True),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    exist_invoice = await GetOneData(
        db.invoices,
        {
            "id_customer": ObjectId(payload["id_customer"]),
            "month": payload["month"],
            "year": payload["year"],
        },
    )
    if exist_invoice:
        raise HTTPException(status_code=400, detail={"message": EXIST_DATA_MESSAGE})

    max_date_of_month = monthrange(
        GetCurrentDateTime().year, GetCurrentDateTime().month
    )[1]
    pipeline = []
    query = {"_id": ObjectId(payload["id_customer"])}

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
                    {
                        "$project": {
                            "name": 1,
                            "price": 1,
                        }
                    },
                    {"$limit": 1},
                ],
                "as": "package",
            }
        }
    )
    pipeline.append(
        {
            "$addFields": {
                "package_amount": {
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
                    },
                    {
                        "$project": {
                            "name": 1,
                            "price": 1,
                        }
                    },
                ],
                "as": "add_on_packages",
            }
        }
    )
    pipeline.append(
        {
            "$addFields": {
                "add_on_package_amount": {
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
                "amount": {"$add": ["$package_amount", "$add_on_package_amount"]}
            },
        }
    )

    # add projection query
    pipeline.append(
        {
            "$project": {
                "name": 1,
                "service_number": 1,
                "due_date": 1,
                "ppn": 1,
                "package": 1,
                "package_amount": 1,
                "add_on_packages": 1,
                "add_on_package_amount": 1,
                "amount": 1,
                "status": 1,
                "unique_code": 1,
            }
        }
    )

    customer_data = await GetAggregateData(db.customers, pipeline)
    if len(customer_data) == 0:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    invoice_exist = 0
    invoice_created = 0
    for customer in customer_data:
        customer_due_date = customer.get("due_date")
        if int(customer_due_date) > max_date_of_month:
            customer_due_date = str(max_date_of_month).zfill(2)

        unique_code = customer.get("unique_code", 1)
        ppn = 0
        paid_leave_discount = 0
        if customer.get("ppn", 0):
            ppn = customer["amount"] * (PPN / 100)

        if customer["status"] == CustomerStatusData.PAID_LEAVE.value:
            paid_leave_discount = customer["amount"] * (
                (100 - PAID_LEAVE_PERCENTAGE) / 100
            )
            customer["amount"] = customer["amount"] - paid_leave_discount

        final_amount = customer["amount"] + ppn + unique_code
        invoice_data = {
            "id_customer": ObjectId(customer["_id"]),
            "name": customer["name"],
            "service_number": customer["service_number"],
            "package": customer["package"],
            "due_date": datetime.strptime(
                f"{payload['year']}-{payload['month']}-{customer_due_date} 23:59:59",
                "%Y-%m-%d %H:%M:%S",
            ),
            "add_on_packages": customer["add_on_packages"],
            "month": payload["month"],
            "year": payload["year"],
            "status": "UNPAID",
            "package_amount": customer["package_amount"],
            "add_on_package_amount": customer["add_on_package_amount"],
            "ppn": ppn,
            "unique_code": unique_code,
            "amount": final_amount,
            "created_at": GetCurrentDateTime(),
        }
        if paid_leave_discount:
            invoice_data["paid_leave_discount"] = paid_leave_discount

        invoice_result = await CreateOneData(db.invoices, invoice_data)
        if not invoice_result.inserted_id:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        invoice_created += 1

    return JSONResponse(
        content={
            "invoice_exist": invoice_exist,
            "invoice_created": invoice_created,
        }
    )


@router.put("/update")
async def update_invoice(
    data: InvoiceUpdateData = Body(..., embed=True),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        payload = data.dict(exclude_unset=True)
        invoice_data = await GetOneData(
            db.invoices, {"_id": ObjectId(payload["id_invoice"])}
        )
        update_data = {
            "id_package": ObjectId(payload["id_package"]),
            "id_add_on_package": [
                ObjectId(item) for item in payload["id_add_on_package"]
            ]
            if "id_add_on_package" in payload and len(payload["id_add_on_package"]) > 0
            else [],
        }
        result = await UpdateOneData(
            db.customers,
            {"_id": ObjectId(payload["id_customer"])},
            {"$set": update_data},
        )
        if not result:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        pipeline = []
        query = {"_id": ObjectId(payload["id_customer"])}
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
                        {
                            "$project": {
                                "name": 1,
                                "price": 1,
                            }
                        },
                        {"$limit": 1},
                    ],
                    "as": "package",
                }
            }
        )
        pipeline.append(
            {
                "$addFields": {
                    "package_amount": {
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
                                    "$in": [
                                        "$_id",
                                        {"$ifNull": ["$$idAddOnPackage", []]},
                                    ]
                                }
                            }
                        },
                        {
                            "$project": {
                                "name": 1,
                                "price": 1,
                            }
                        },
                    ],
                    "as": "add_on_packages",
                }
            }
        )
        pipeline.append(
            {
                "$addFields": {
                    "add_on_package_amount": {
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
                    "amount": {"$add": ["$package_amount", "$add_on_package_amount"]}
                },
            }
        )

        # add projection query
        pipeline.append(
            {
                "$project": {
                    "name": 1,
                    "service_number": 1,
                    "due_date": 1,
                    "ppn": 1,
                    "package": 1,
                    "package_amount": 1,
                    "add_on_packages": 1,
                    "add_on_package_amount": 1,
                    "amount": 1,
                    "unique_code": 1,
                }
            }
        )

        customer_data, _ = await GetManyData(db.customers, pipeline)
        for customer in customer_data:
            ppn = 0
            if customer.get("ppn", 0):
                ppn = customer["amount"] * (PPN / 100)
            final_amount = customer["amount"] + ppn + invoice_data["unique_code"]
            invoice_update_data = {
                "package": customer["package"],
                "add_on_packages": customer["add_on_packages"],
                "package_amount": customer["package_amount"],
                "add_on_package_amount": customer["add_on_package_amount"],
                "ppn": ppn,
                "amount": final_amount,
            }

            invoice_result = await UpdateOneData(
                db.invoices,
                {"_id": ObjectId(payload["id_invoice"])},
                {"$set": invoice_update_data},
            )
            if not invoice_result:
                raise HTTPException(
                    status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
                )

            return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.put("/update/status")
async def update_invoice_status(
    id: str,
    status: InvoiceStatusData,
    description: str = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    decoded_id = base64.b64decode(id).decode("utf-8")
    invoice_ids = [ObjectId(item.strip()) for item in decoded_id.split(",")]
    update_data = {}
    if status == InvoiceStatusData.PAID.value:
        update_data = {
            "$set": {
                "status": status,
                "payment.method": PaymentMethodData.CASH.value,
                "payment.description": description,
                "payment.paid_at": GetCurrentDateTime(),
                "payment.confirmed_by": current_user.email,
                "payment.confirmed_at": GetCurrentDateTime(),
            },
        }
    elif status == InvoiceStatusData.UNPAID.value:
        for id in invoice_ids:
            exist_data = await GetOneData(db.invoices, {"_id": id})
            if (
                exist_data
                and "payment" in exist_data
                and "image_url" in exist_data["payment"]
            ):
                RemoveFilePath(exist_data["payment"]["image_url"])

            await DeleteOneData(db.invoice_fees, {"id_invoice": ObjectId(id)})

        update_data = {
            "$set": {
                "status": status,
            },
            "$unset": {
                "payment": "",
            },
        }

    result = await UpdateManyData(
        db.invoices, {"_id": {"$in": invoice_ids}}, update_data
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    if status == InvoiceStatusData.PAID.value:
        for id in invoice_ids:
            asyncio.create_task(SendTelegramPaymentMessage(db, id))
            invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id)})
            if invoice_data:
                customer_data = await GetOneData(
                    db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
                )
                if customer_data:
                    status = customer_data.get("status", None)
                    if status != CustomerStatusData.ACTIVE and CustomerStatusData.FREE:
                        await UpdateOneData(
                            db.customers,
                            {"_id": ObjectId(invoice_data["id_customer"])},
                            {"$set": {"status": CustomerStatusData.ACTIVE.value}},
                        )
                        await ActivateMikrotikPPPSecret(db, customer_data, False)

                    await CheckMitraFee(db, customer_data, id)

    if len(invoice_ids) > 0:
        asyncio.create_task(SendWhatsappPaymentSuccessMessage(db, invoice_ids))

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/update/owner-verified-status")
async def update_invoice_owner_verified_status(
    id: str,
    owner_verified_status: InvoiceOwnerVerifiedStatusData,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    decoded_id = base64.b64decode(id).decode("utf-8")
    invoice_ids = [ObjectId(item.strip()) for item in decoded_id.split(",")]
    update_data = {"owner_verified_status": owner_verified_status}

    result = await UpdateManyData(
        db.invoices, {"_id": {"$in": invoice_ids}}, {"$set": update_data}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/update/collector-status")
async def update_invoice_collector_status(
    id: str,
    status: InvoiceStatusData,
    description: Optional[str] = None,
    assigned_to: Optional[str] = None,
    repeat_monthly: Optional[bool] = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if status not in (InvoiceStatusData.COLLECTING, InvoiceStatusData.COLLECTED):
        raise HTTPException(
            status_code=400, detail={"message": "Invalid collector status."}
        )

    try:
        decoded = base64.b64decode(id).decode("utf-8")
        id_list: List[ObjectId] = [
            ObjectId(i.strip()) for i in decoded.split(",") if i.strip()
        ]
        if not id_list:
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Invalid ID format."})

    collector_data = {
        "description": description,
        "updated_by": current_user.email,
        "updated_at": GetCurrentDateTime(),
        "status": status.value,
    }

    if assigned_to:
        collector_data["assigned_to"] = assigned_to

    if status == InvoiceStatusData.COLLECTED:
        collector_data["collected_at"] = GetCurrentDateTime()

    if status == InvoiceStatusData.COLLECTING and repeat_monthly is not None:
        collector_data["repeat_monthly"] = repeat_monthly

    update_data = {
        "$set": {
            "status": status.value,
            "collector": collector_data,
        }
    }

    result = await UpdateManyData(db.invoices, {"_id": {"$in": id_list}}, update_data)

    if not result or getattr(result, "modified_count", 0) == 0:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(
        content={
            "message": DATA_HAS_UPDATED_MESSAGE,
            "modified_count": result.modified_count,
        }
    )


@router.delete("/delete")
async def delete_invoice(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    decoded_id = base64.b64decode(id).decode("utf-8")
    id_list = [ObjectId(item.strip()) for item in decoded_id.split(",")]
    for id in id_list:
        exist_data = await GetOneData(db.invoices, {"_id": id})
        if (
            exist_data
            and "payment" in exist_data
            and "image_url" in exist_data["payment"]
        ):
            RemoveFilePath(exist_data["payment"]["image_url"])

    result = await DeleteManyData(db.invoices, {"_id": {"$in": id_list}})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    await DeleteManyData(db.incomes, {"id_invoice": {"$in": id_list}})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
