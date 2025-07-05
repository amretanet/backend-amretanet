import base64
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Body
from fastapi.responses import JSONResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime
from typing import Optional
from app.modules.mikrotik import ActivateMikrotikPPPSecret
from app.modules.generals import DateIDFormatter, GetCurrentDateTime, ThousandSeparator
from app.models.customers import CustomerStatusData
from app.models.notifications import NotificationTypeData
from typing import Optional, List


from app.modules.crud_operations import (
    CreateOneData,
    DeleteManyData,
    DeleteOneData,
    GetAggregateData,
    GetManyData,
    GetOneData,
    UpdateManyData,
    UpdateOneData,
)
from app.models.bill import (
    BillPayOffData,
    BillStatusData,
    MarkCollectedBody
)

from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    EXIST_DATA_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    NOT_FOUND_MESSAGE,
)


from app.models.users import UserData
from app.routes.v1.auth_routes import GetCurrentUser 
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase  
def convert_objectid(doc):
    doc["_id"] = str(doc["_id"])
    if "customer_id" in doc:
        doc["customer_id"] = str(doc["customer_id"])
    return doc


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
            }
        ]

    query["status"] = status if status else "COLLECTING"

    if month:
        query["month"] = month
    if year:
        query["year"] = year

    pipeline = [
        {"$match": query},
        {
            "$lookup": {
                "from": "customers",
                "let": {"customerId": "$id_customer"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$customerId"]}}},
                    {"$project": {"name": 1, "status": 1}}
                ],
                "as": "customer"
            }
        },
        {"$unwind": "$customer"},
        {"$sort": {sort_key: 1 if sort_direction == "asc" else -1}}
    ]

    bill_data, count = await GetManyData(
        db.invoices, pipeline, {}, {"page": page, "items": items}
    )

    pagination_info = {
        "page": page,
        "items": items,
        "count": count,
    }

    return JSONResponse(
        content={
            "bill_data": bill_data,
            "pagination_info": pagination_info
        }
    )


@router.get("/detail/{id}")
async def get_bill_detail(
    id: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        object_id = ObjectId(id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid bill ID format")

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
            "add_on_packages": 1,
            "payment": 1,
            "customer": 1,
            "created_at": 1,
            "collector": 1, 
        }

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
    invoice_id = ObjectId(id)

    invoice_data = await GetOneData(db.invoices, {"_id": invoice_id})
    if not invoice_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    payload = data.dict(exclude_unset=True)

    # Calculate total amount
    invoice_data["amount"] = (
        invoice_data.get("package_amount", 0)
        + invoice_data.get("add_on_package_amount", 0)
        + payload["unique_code"]
    )

    # Prepare update payload
    update_data = {
        "status": BillStatusData.PAID,
        "amount": invoice_data["amount"],
        "unique_code": payload["unique_code"],
        "payment": {
            "method": payload["method"],
            "description": payload["description"],
            "paid_at": GetCurrentDateTime(),
            "confirmed_by": current_user.email,
            "confirmed_at": GetCurrentDateTime(),
        },
    }

    if "image_url" in payload:
        update_data["payment"]["image_url"] = payload["image_url"]

    result = await UpdateOneData(
        db.invoices, {"_id": invoice_id}, {"$set": update_data}, upsert=True
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    # Save income record
    income_data = {
        "id_invoice": invoice_id,
        "nominal": invoice_data["amount"],
        "category": "KOLEKSI TAGIHAN",
        "description": f"Pembayaran Tagihan dengan Nomor Layanan {invoice_data.get('service_number', '-')} a/n {invoice_data.get('name', '-')}, Periode {DateIDFormatter(invoice_data.get('due_date'))}",
        "method": payload["method"],
        "date": GetCurrentDateTime(),
        "id_receiver": ObjectId(current_user.id),
        "created_at": GetCurrentDateTime(),
    }

    await UpdateOneData(
        db.incomes, {"id_invoice": invoice_id}, {"$set": income_data}, upsert=True
    )

    # Update customer status if needed
    customer_data = await GetOneData(
        db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
    )
    if customer_data:
        status = customer_data.get("status")
        if status != CustomerStatusData.ACTIVE and CustomerStatusData.FREE:
            await UpdateOneData(
                db.customers,
                {"_id": ObjectId(invoice_data["id_customer"])},
                {"$set": {"status": CustomerStatusData.ACTIVE.value}},
            )
            await ActivateMikrotikPPPSecret(db, customer_data, False)

        await CheckMitraFee(db, customer_data, id)

        # Add internal notification
        notification_data = {
            "id_user": ObjectId(customer_data["id_user"]),
            "title": "Tagihan Telah Dibayar",
            "description": f"Tagihan anda senilai Rp{ThousandSeparator(invoice_data['amount'])} telah dikonfirmasi!",
            "type": NotificationTypeData.OTHER.value,
            "is_read": 0,
            "created_at": GetCurrentDateTime(),
        }

        await CreateOneData(db.notifications, notification_data)

    return JSONResponse(content={"message": "Tagihan telah dilunasi."})


@router.put("/mark-collected")
async def mark_bill_as_collected(
    data: MarkCollectedBody,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    # 🔍 Decode & validate ID
    try:
        decoded = base64.b64decode(data.id).decode("utf-8")
        id_list: List[ObjectId] = [ObjectId(i.strip()) for i in decoded.split(",") if i.strip()]
        if not id_list:
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail={"message": "Invalid ID format."})

    invoices = await db.invoices.find({"_id": {"$in": id_list}}).to_list(length=len(id_list))

    if not invoices:
        raise HTTPException(status_code=404, detail={"message": "Invoices not found."})

    modified_count = 0

    for invoice in invoices:
        assigned_to = invoice.get("collector", {}).get("assigned_to")

        collector_data = {
            "description": data.description,
            "updated_by": current_user.email,
            "updated_at": GetCurrentDateTime(),
            "collected_at": GetCurrentDateTime(),
            "status": BillStatusData.COLLECTED.value,
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

    return JSONResponse(content={
        "message": "Tagihan berhasil ditandai sebagai COLLECTED",
        "modified_count": modified_count
    })

@router.patch("/bills/{bill_id}/pay")
async def mark_as_paid(
    bill_id: str,
    db: AsyncIOMotorDatabase = Depends(GetAmretaDatabase),
    current_user: UserData = Depends(GetCurrentUser)
):
    result = await db.bills.update_one(
        {"_id": ObjectId(bill_id), "customer_id": str(current_user.id)},
        {"$set": {"status": "paid", "updated_at": datetime.utcnow()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Bill not found or not modified")
    return {"message": "Bill marked as paid"}

@router.patch("/bills/{bill_id}/collect")
async def mark_as_collected(
    bill_id: str,
    db: AsyncIOMotorDatabase = Depends(GetAmretaDatabase),
    current_user: UserData = Depends(GetCurrentUser)
):
    result = await db.bills.update_one(
        {"_id": ObjectId(bill_id), "customer_id": str(current_user.id)},
        {"$set": {"status": "collected", "updated_at": datetime.utcnow()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Bill not found or not modified")
    return {"message": "Bill marked as collected"}

@router.post("/bills/{bill_id}/receipt")
async def upload_receipt(
    bill_id: str,
    file: UploadFile = File(...),
    db: AsyncIOMotorDatabase = Depends(GetAmretaDatabase),
    current_user: UserData = Depends(GetCurrentUser)
):
    # Save the uploaded file to "uploads/" folder
    uploads_dir = "uploads"
    os.makedirs(uploads_dir, exist_ok=True)  # Create if not exists
    file_path = os.path.join(uploads_dir, f"{bill_id}_{file.filename}")

    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Update bill with receipt URL
    result = await db.bills.update_one(
        {"_id": ObjectId(bill_id), "customer_id": str(current_user.id)},
        {"$set": {"receipt_url": file_path, "updated_at": datetime.utcnow()}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Bill not found or not modified")

    return {"message": "Receipt uploaded successfully", "receipt_url": file_path}

async def CheckMitraFee(db, customer_data, id_invoice):
    invoice_data, count = await GetManyData(
        db.invoices,
        [{"$match": {"id_customer": ObjectId(customer_data.get("_id"))}}],
        {"_id": 1},
    )
    if count <= 1:
        return

    if customer_data.get("referral", None):
        referral_user = await GetOneData(
            db.users, {"referral": customer_data.get("referral")}
        )
        if referral_user and referral_user.get("role") == UserRole.MITRA:
            package_data = await GetOneData(
                db.packages,
                {"_id": ObjectId(customer_data.get("id_package"))},
            )
            if package_data:
                package_fee = package_data.get("price", {}).get("mitra_fee", 0)
                mitra_fee = referral_user.get("saldo", 0) + package_fee
                await UpdateOneData(
                    db.users,
                    {"referral": customer_data.get("referral")},
                    {"$set": {"saldo": mitra_fee}},
                )
                await CreateOneData(
                    db.invoice_fees,
                    {
                        "id_customer": ObjectId(customer_data.get("_id")),
                        "id_invoice": ObjectId(id_invoice),
                        "id_user": ObjectId(referral_user.get("_id")),
                        "referral": referral_user.get("referral"),
                        "fee": package_fee,
                        "created_at": GetCurrentDateTime(),
                    },
                )
