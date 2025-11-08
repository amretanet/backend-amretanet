import asyncio
import base64
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from typing import Any, Dict
from app.modules.mikrotik import ActivateMikrotikPPPSecret
from app.modules.generals import DateIDFormatter, GetCurrentDateTime, ThousandSeparator
from app.models.customers import CustomerStatusData
from app.models.notifications import NotificationTypeData
from typing import List
from dateutil.relativedelta import relativedelta
from app.models.payments import PaymentMethodData
from app.models.users import UserData, UserRole
from app.routes.v1.payment_routes import CheckMitraFee
from app.modules.crud_operations import (
    CreateOneData,
    GetAggregateData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.whatsapp_message import (
    SendWhatsappPaymentSuccessBillMessage,
)
from app.models.bill import (
    BillPayOffData,
    BillStatusData,
    MarkCollectedBody,
    MarkApprovedBody,
)

from app.modules.response_message import (
    FORBIDDEN_ACCESS_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
)
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
ALLOWED_STATUSES = ["PAID", "COLLECTED"] 

router = APIRouter(prefix="/bills", tags=["Bill Collector"])

@router.get("")
async def get_bills(
    id_customer: str = None,
    key: str = None,
    month: str = None,
    year: str = None,
    status: str = None,
    page: int = 1,
    items: int = 10,
    sort_key: str = "due_date",
    sort_direction: str = "asc",
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorDatabase = Depends(GetAmretaDatabase)
):
    query: Dict[str, Any] = {}

    # Filter berdasarkan ID Customer
    if id_customer:
        query["id_customer"] = ObjectId(id_customer)

    # Filter pencarian berdasarkan nama atau service_number
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

    # Filter status
    if status:
        query["collector.status"] = status
    else:
        query["collector.status"] = {"$in": ["COLLECTING", "COLLECTED", "APPROVED"]}

    # Filter bulan dan tahun
    if month:
        query["month"] = month
    if year:
        query["year"] = year

    # 🔐 Filter berdasarkan role user
    if current_user.role != UserRole.OWNER.value:
        query["collector.assigned_to"] = current_user.email

    pipeline = [
        {"$match": query},
        {"$addFields": {"status": "$collector.status"}},
        {
            "$lookup": {
                "from": "customers",
                "let": {"customerId": "$id_customer"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$customerId"]}}},
                    {"$project": {"name": 1, "status": 1}},
                ],
                "as": "customer",
            }
        },
        {"$unwind": "$customer"},
        {"$sort": {sort_key: 1 if sort_direction == "asc" else -1}},
    ]

    bill_data, count = await GetManyData(
        db.invoices, pipeline, {}, {"page": page, "items": items}
    )

    return JSONResponse(
        content={
            "bill_data": bill_data,
            "pagination_info": {
                "page": page,
                "items": items,
                "count": count,
            },
        }
    )


@router.get("/assigned")
async def get_assigned_bills(
    assigned_to: str,
    page: int = 1,
    items: int = 10,
    sort_key: str = "due_date",
    sort_direction: str = "asc",
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorDatabase = Depends(GetAmretaDatabase),
):

    if current_user.role not in [UserRole.OWNER.value, UserRole.BILL_COLLECTOR.value]:
        raise HTTPException(status_code=403, detail="Forbidden")

    if current_user.role == UserRole.BILL_COLLECTOR.value:
        assigned_to = current_user.email

    if not assigned_to:
        raise HTTPException(status_code=400, detail="assigned_to parameter required")

    query = {"collector.assigned_to": assigned_to}

    pipeline = [
        {"$match": query},
        {"$addFields": {"status": "$collector.status"}},
        {
            "$lookup": {
                "from": "customers",
                "let": {"customerId": "$id_customer"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$customerId"]}}},
                    {"$project": {"name": 1, "status": 1}},
                ],
                "as": "customer",
            }
        },
        {"$unwind": "$customer"},
        {"$sort": {sort_key: 1 if sort_direction == "asc" else -1}},
    ]

    bill_data, count = await GetManyData(
        db.invoices, pipeline, {}, {"page": page, "items": items}
    )

    return JSONResponse(
        content={
            "bill_data": bill_data,
            "pagination_info": {
                "page": page,
                "items": items,
                "count": count,
            },
        }
    )


@router.get("/assigned-users")
async def get_assigned_users(
    db: AsyncIOMotorDatabase = Depends(GetAmretaDatabase),
    current_user: UserData = Depends(GetCurrentUser),
):
    # 🔐 Only OWNER can access
    if current_user.role != UserRole.OWNER.value:
        raise HTTPException(status_code=403, detail="Forbidden")

    pipeline = [
        {"$match": {"collector.assigned_to": {"$ne": None}}},
        {
            "$group": {
                "_id": "$collector.assigned_to",
                "total_pembayaran": {
                    "$sum": {
                        "$cond": [
                            {"$in": ["$status", ALLOWED_STATUSES]},
                            {"$ifNull": ["$amount", 0]},
                            0,
                        ]
                    }
                },
                "unique_customers": {"$addToSet": "$id_customer"},
            }
        },
        {
            "$project": {
                "_id": 1,
                "total_pembayaran": 1,
                "total_pelanggan": {"$size": "$unique_customers"},
            }
        },
        {
            "$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "email",
                "as": "user",
            }
        },
        {"$unwind": {"path": "$user", "preserveNullAndEmptyArrays": False}},
        {
            "$project": {
                "email": "$_id",
                "name": "$user.name",
                "role": "$user.role",
                "total_pembayaran": 1,
                "total_pelanggan": 1,
                "_id": 0,
            }
        },
        {"$sort": {"name": 1}},
    ]

    assigned_users_raw = await db.invoices.aggregate(pipeline).to_list(length=None)

    assigned_users = [
        {
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "total_pembayaran": user["total_pembayaran"],
            "total_pelanggan": user["total_pelanggan"],
        }
        for user in assigned_users_raw
    ]

    return JSONResponse(content={"assigned_users": assigned_users})

@router.get("/detail/{id}")
async def get_bill_detail(
    id: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    object_id = ObjectId(id)

    bill_data = await GetOneData(
        db.invoices,
        {"_id": object_id},
        {
            "name": 1,
            "service_number": 1,
            "due_date": 1,
            "status": 1,
            "amount": 1,
            "month": 1,
            "year": 1,
            "package": 1,
            "unique_code": 1,
            "add_on_packages": 1,
            "payment": 1,
            "customer": 1,
            "created_at": 1,
            "collector": 1,
        },
    )

    if not bill_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    return JSONResponse(content={"bill_data": bill_data})


@router.put("/pay-off/{id}")
async def pay_off_bill(
    id: str,
    data: BillPayOffData = Body(..., embed=True),
    current_user=Depends(GetCurrentUser),
    db=Depends(GetAmretaDatabase),
):
    try:
        invoice_id = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid invoice ID")

    invoice_data = await GetOneData(db.invoices, {"_id": invoice_id})
    if not invoice_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    payload = data.dict(exclude_unset=True)

    unique_code = payload.get("unique_code") or 0
    total_amount = (
        invoice_data.get("package_amount", 0) +
        invoice_data.get("add_on_package_amount", 0) +
        unique_code
    )

    update_data = {
        "status": "PAID",              
        "collector.status": "PAID",    
        "amount": total_amount,
        "unique_code": unique_code,
        "payment": {
            "method": "CASH",
            "description": payload.get("description", ""),
            "paid_at": GetCurrentDateTime(),
            "confirmed_by": current_user.email,
            "confirmed_at": GetCurrentDateTime(),
        },
    }

    if "image_url" in payload:
        update_data["payment"]["image_url"] = payload["image_url"]

    result = await db.invoices.update_one(
        {"_id": invoice_id},
        {"$set": update_data}
    )

    if result.modified_count == 0:
        print(f"Invoice {invoice_id} already has the same status or amount.")

    income_data = {
        "id_invoice": invoice_id,
        "nominal": total_amount,
        "category": "KOLEKSI TAGIHAN",
        "description": f"Pembayaran Tagihan dengan Nomor Layanan {invoice_data.get('service_number', '-')}"
                       f" a/n {invoice_data.get('name', '-')}, Periode {DateIDFormatter(invoice_data.get('due_date'))}",
        "method": "CASH",
        "date": GetCurrentDateTime(),
        "id_receiver": ObjectId(current_user.id),
        "created_at": GetCurrentDateTime(),
    }
    await db.incomes.update_one({"id_invoice": invoice_id}, {"$set": income_data}, upsert=True)

    customer_data = await GetOneData(db.customers, {"_id": ObjectId(invoice_data["id_customer"])})
    if customer_data:
        if customer_data.get("status") != CustomerStatusData.ACTIVE.value:
            await db.customers.update_one(
                {"_id": ObjectId(invoice_data["id_customer"])},
                {"$set": {"status": CustomerStatusData.ACTIVE.value}}
            )
            await ActivateMikrotikPPPSecret(db, customer_data, False)

        await CheckMitraFee(db, customer_data, id)

        notification_data = {
            "id_user": ObjectId(customer_data["id_user"]),
            "title": "Tagihan Telah Dibayar",
            "description": f"Tagihan anda senilai Rp{ThousandSeparator(total_amount)} telah dikonfirmasi!",
            "type": NotificationTypeData.OTHER.value,
            "is_read": 0,
            "created_at": GetCurrentDateTime(),
        }
        await CreateOneData(db.notifications, notification_data)

    return JSONResponse(content={"message": "Tagihan telah dilunasi dan disetujui."})

@router.put("/mark-collected")
async def mark_bill_as_collected(
    data: MarkCollectedBody,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        decoded = base64.b64decode(data.id).decode("utf-8")
        invoice_ids: List[ObjectId] = [
            ObjectId(i.strip()) for i in decoded.split(",") if i.strip()
        ]
        if not invoice_ids:
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Invalid ID format."})

    invoices = await db.invoices.find({"_id": {"$in": invoice_ids}}).to_list(
        length=len(invoice_ids)
    )

    if not invoices:
        raise HTTPException(status_code=404, detail={"message": "Invoices not found."})

    modified_count = 0

    for invoice in invoices:
        now = GetCurrentDateTime()
        assigned_to = invoice.get("collector", {}).get("assigned_to")

        collector_data = {
            "description": data.description,
            "updated_by": current_user.email,
            "updated_at": now,
            "collected_at": now,
            "status": BillStatusData.COLLECTED.value,
        }

        if assigned_to:
            collector_data["assigned_to"] = assigned_to

        update_data = {
            "$set": {
                "status": BillStatusData.PAID.value,
                "collector": collector_data,
                "payment": {
                    "method": PaymentMethodData.CASH.value,
                    "description": data.description,
                    "paid_at": now,
                    "confirmed_by": current_user.email,
                    "confirmed_at": now,
                },
            }
        }

        result = await db.invoices.update_one({"_id": invoice["_id"]}, update_data)
        if result.modified_count > 0:
            modified_count += 1

            invoice_id = invoice["_id"]

            updated_invoice = await GetOneData(db.invoices, {"_id": invoice_id})
            if updated_invoice:
                customer = await GetOneData(
                    db.customers, {"_id": ObjectId(updated_invoice["id_customer"])}
                )
                if customer:
                    status = customer.get("status")
                    if (
                        status != CustomerStatusData.ACTIVE
                        and status == CustomerStatusData.FREE
                    ):
                        await UpdateOneData(
                            db.customers,
                            {"_id": customer["_id"]},
                            {"$set": {"status": CustomerStatusData.ACTIVE.value}},
                        )
                        await ActivateMikrotikPPPSecret(db, customer, False)

                notification_data = {
                    "id_invoice": invoice_id,
                    "type": NotificationTypeData.PAYMENT_CONFIRM.value,
                    "title": "Pembayaran Dikonfirmasi",
                    "description": f"{customer.get('name', 'Pelanggan')} telah membayar tagihan dan bill telah diambil oleh {current_user.name}.",
                    "is_read": 0,
                    "created_at": now,
                }

                admin_users = await GetAggregateData(
                    db.users, [{"$match": {"role": UserRole.OWNER}}]
                )

                for user in admin_users:
                    notification_data["id_user"] = ObjectId(user["_id"])
                    await CreateOneData(db.notifications, notification_data.copy())

    if modified_count == 0:
        raise HTTPException(
            status_code=400,
            detail={"message": "Tidak ada tagihan yang berhasil diperbarui."},
        )
    if len(invoice_ids) > 0:
        asyncio.create_task(SendWhatsappPaymentSuccessBillMessage(db, invoice_ids))

    return JSONResponse(
        content={
            "message": "Tagihan berhasil ditandai sebagai COLLECTED",
            "modified_count": modified_count,
        }
    )


@router.put("/mark-approved")
async def mark_bill_as_approved(
    data: MarkApprovedBody,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        decoded = base64.b64decode(data.id).decode("utf-8")
        id_list: List[ObjectId] = [
            ObjectId(i.strip()) for i in decoded.split(",") if i.strip()
        ]
        if not id_list:
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Invalid ID format."})

    invoices = await db.invoices.find({"_id": {"$in": id_list}}).to_list(
        length=len(id_list)
    )

    if not invoices:
        raise HTTPException(status_code=404, detail={"message": "Invoices not found."})

    modified_count = 0

    for invoice in invoices:
        collector = invoice.get("collector", {})
        assigned_to = collector.get("assigned_to")

        collector_data = {
            "description": collector.get("description", ""),
            "approved_description": data.approved_description,
            "updated_by": current_user.email,
            "updated_at": GetCurrentDateTime(),
            "collected_at": GetCurrentDateTime(),
            "status": BillStatusData.APPROVED.value,
            "approved_by": current_user.email,
            "approved_at": GetCurrentDateTime(),
        }

        if assigned_to:
            collector_data["assigned_to"] = assigned_to

        update_data = {
            "$set": {
                "status": BillStatusData.PAID.value,
                "collector": collector_data,
            }
        }

        result = await db.invoices.update_one({"_id": invoice["_id"]}, update_data)
        if result.modified_count > 0:
            modified_count += 1

    if modified_count == 0:
        raise HTTPException(status_code=500, detail={"message": "No invoices updated."})

    return JSONResponse(
        content={
            "message": "Tagihan berhasil disetujui dan ditandai sebagai PAID",
            "modified_count": modified_count,
        }
    )


@router.post("/bill-collector/auto-repeat")
async def auto_repeat_collector_status(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    today = GetCurrentDateTime()

    query = {
        "collector.repeat_monthly": True,
        "collector.status": "COLLECTED",
        "due_date": {"$lt": today},
    }

    invoices = db.invoices.find(query)

    updated_count = 0
    async for invoice in invoices:
        current_due = invoice.get("due_date")
        if not current_due:
            continue

        new_due_date = current_due + relativedelta(months=1)

        update_data = {
            "$set": {
                "status": "COLLECTING",
                "due_date": new_due_date,
                "collector.status": "COLLECTING",
                "collector.updated_at": GetCurrentDateTime(),
            },
            "$unset": {"collector.collected_at": "", "collector.description": ""},
        }

        await db.invoices.update_one({"_id": invoice["_id"]}, update_data)
        updated_count += 1

    return {
        "message": "Repeat monthly collector status updated.",
        "updated_count": updated_count,
    }


@router.delete("/delete")
async def delete_invoice_collector_data(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )

    try:
        decoded_id = base64.b64decode(id).decode("utf-8")
        id_list = [
            ObjectId(item.strip()) for item in decoded_id.split(",") if item.strip()
        ]
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Invalid ID format."})

    result = await db.invoices.update_many(
        {"_id": {"$in": id_list}}, {"$unset": {"collector": ""}}
    )

    if result.modified_count == 0:
        raise HTTPException(
            status_code=404,
            detail={"message": "Tidak ada data collector yang dihapus."},
        )

    return JSONResponse(
        content={
            "message": f"Data collector berhasil dihapus dari {result.modified_count} tagihan."
        }
    )
