import asyncio
import base64
import hmac
import json
from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Request,
)
import urllib.parse
from app.models.notifications import NotificationTypeData
from app.models.invoices import InvoiceOwnerVerifiedStatusData, InvoiceStatusData
from app.models.payments import (
    PaymentPayOffData,
    RequestConfirmData,
)
from app.models.bill import BillStatusData

from app.models.customers import CustomerStatusData
from app.modules.response_message import NOT_FOUND_MESSAGE, SYSTEM_ERROR_MESSAGE
from fastapi.responses import JSONResponse
from app.models.users import UserData, UserRole
from app.modules.generals import DateIDFormatter, GetCurrentDateTime, ThousandSeparator
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import (
    CreateOneData,
    GetAggregateData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.models.payments import PaymentMethodData
from app.modules.mikrotik import ActivateMikrotikPPPSecret
from app.modules.whatsapp_message import (
    SendWhatsappPaymentSuccessMessage,
)
import requests
from dotenv import load_dotenv
import hashlib
import os
from app.modules.telegram_message import SendTelegramPaymentMessage

load_dotenv()

# ipaymu config
IPAYMU_API_DOMAIN = os.getenv("IPAYMU_API_DOMAIN")
IPAYMU_VA = os.getenv("IPAYMU_VA")
IPAYMU_API_TOKEN = os.getenv("IPAYMU_API_TOKEN")
IPAYMU_RETURN_URL = os.getenv("IPAYMU_RETURN_URL")
IPAYMU_CALLBACK_URL = os.getenv("IPAYMU_CALLBACK_URL")
# moota config
MOOTA_CALLBACK_SECRET_KEY = os.getenv("MOOTA_CALLBACK_SECRET_KEY")
MOOTA_API_TOKEN = os.getenv("MOOTA_API_TOKEN")
MOOTA_BANK_ACCOUNT_ID = os.getenv("MOOTA_BANK_ACCOUNT_ID")
# autoconfirm config
AUTOCONFIRM_USER_ID = os.getenv("AUTOCONFIRM_USER_ID")
AUTOCONFIRM_USER_EMAIL = os.getenv("AUTOCONFIRM_USER_EMAIL")

router = APIRouter(prefix="/payment", tags=["Payments"])


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


@router.put("/pay-off/{id}")
async def pay_off_payment(
    id: str,
    data: PaymentPayOffData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id)})
    if not invoice_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    payload = data.dict(exclude_unset=True)
    invoice_data["amount"] = (
        invoice_data["package_amount"]
        + invoice_data["add_on_package_amount"]
        + payload["unique_code"]
    )

    now = GetCurrentDateTime()

    update_data = {
        "status": InvoiceStatusData.PAID,
        "unique_code": payload["unique_code"],
        "amount": invoice_data["amount"],
        "payment": {
            "method": payload["method"],
            "description": payload["description"],
            "paid_at": now,
            "confirmed_by": current_user.email,
            "confirmed_at": now,
        },
        "owner_verified_status": InvoiceOwnerVerifiedStatusData.PENDING.value,
    }
    if current_user.role == UserRole.OWNER.value:
        update_data["owner_verified_status"] = (
            InvoiceOwnerVerifiedStatusData.ACCEPTED.value
        )

    if "image_url" in payload:
        update_data["payment"]["image_url"] = payload["image_url"]

    if "collector" in invoice_data and invoice_data["collector"]:
        collector_data = invoice_data["collector"]
        collector_data["status"] = BillStatusData.APPROVED.value
        update_data["collector"] = collector_data

    result = await UpdateOneData(
        db.invoices,
        {"_id": ObjectId(id)},
        {"$set": update_data},
        upsert=True,
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    income_data = {
        "id_invoice": ObjectId(id),
        "nominal": invoice_data.get("amount", 0),
        "category": "BAYAR TAGIHAN",
        "description": f"Pembayaran Tagihan dengan Nomor Layanan {invoice_data.get('service_number', '-')} a/n {invoice_data.get('name', '-')}, Periode {DateIDFormatter(invoice_data.get('due_date'))}",
        "method": payload["method"],
        "date": now,
        "id_receiver": ObjectId(current_user.id),
        "created_at": now,
    }
    await UpdateOneData(
        db.incomes, {"id_invoice": ObjectId(id)}, {"$set": income_data}, upsert=True
    )

    asyncio.create_task(SendWhatsappPaymentSuccessMessage(db, [id]))
    asyncio.create_task(SendTelegramPaymentMessage(db, id))
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

        notification_data = {
            "id_user": ObjectId(customer_data["id_user"]),
            "title": "Tagihan Telah Dibayar",
            "description": f"Tagihan anda senilai Rp{ThousandSeparator(invoice_data.get('amount', 0))} telah dikonfirmasi!",
            "type": NotificationTypeData.OTHER.value,
            "is_read": 0,
            "created_at": now,
        }
        await CreateOneData(db.notifications, notification_data)

    return JSONResponse(content={"message": "Pembayaran Telah Dilunasi!"})


@router.put("/confirm")
async def confirm_payment(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    decoded_id = base64.b64decode(id).decode("utf-8")
    id_list = [item.strip() for item in decoded_id.split(",")]
    for id in id_list:
        invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id)})
        if not invoice_data:
            continue

        update_data = {
            "status": InvoiceStatusData.PAID,
            "payment.confirmed_by": current_user.email,
            "payment.confirmed_at": GetCurrentDateTime(),
            "owner_verified_status": InvoiceOwnerVerifiedStatusData.PENDING.value,
        }
        if current_user.role == UserRole.OWNER.value:
            update_data["owner_verified_status"] = (
                InvoiceOwnerVerifiedStatusData.ACCEPTED.value
            )

        result = await UpdateOneData(
            db.invoices,
            {"_id": ObjectId(id)},
            {"$set": update_data},
            upsert=True,
        )
        if not result:
            continue

        income_data = {
            "id_invoice": ObjectId(id),
            "nominal": invoice_data.get("amount", 0),
            "category": "BAYAR TAGIHAN",
            "description": f"Pembayaran Tagihan dengan Nomor Layanan {invoice_data.get('service_number', '-')} a/n {invoice_data.get('name', '-')}, Periode {DateIDFormatter(invoice_data.get('due_date'))}",
            "method": PaymentMethodData.TRANSFER.value,
            "date": GetCurrentDateTime(),
            "id_receiver": ObjectId(current_user.id),
            "created_at": GetCurrentDateTime(),
        }
        await UpdateOneData(
            db.incomes, {"id_invoice": ObjectId(id)}, {"$set": income_data}, upsert=True
        )

        asyncio.create_task(SendWhatsappPaymentSuccessMessage(db, [id]))
        asyncio.create_task(SendTelegramPaymentMessage(db, id))

        customer_data = await GetOneData(
            db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
        )
        if not customer_data:
            continue

        status = customer_data.get("status", None)
        if status != CustomerStatusData.ACTIVE and status != CustomerStatusData.FREE:
            await UpdateOneData(
                db.customers,
                {"_id": ObjectId(invoice_data["id_customer"])},
                {"$set": {"status": CustomerStatusData.ACTIVE.value}},
            )
            await ActivateMikrotikPPPSecret(db, customer_data, False)

        await CheckMitraFee(db, customer_data, id)

        notification_data = {
            "id_user": ObjectId(customer_data["id_user"]),
            "title": "Tagihan Telah Dibayar",
            "description": f"Tagihan anda senilai Rp{ThousandSeparator(invoice_data.get('amount', 0))} telah dkonfirmasi!",
            "type": NotificationTypeData.OTHER.value,
            "is_read": 0,
            "created_at": GetCurrentDateTime(),
        }
        await CreateOneData(db.notifications, notification_data)
    return JSONResponse(content={"message": "Pembayaran Telah Dikonfirmasi!"})


@router.put("/request-confirm/{id_invoice}")
async def request_confirm_payment(
    id_invoice: str,
    data: RequestConfirmData = Body(..., embed=True),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        payload = data.dict(exclude_unset=True)
        exist_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
        if not exist_data:
            raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

        payload["paid_at"] = GetCurrentDateTime()

        update_data = {
            "status": InvoiceStatusData.PENDING.value,
            "payment": payload,
        }
        result = await UpdateOneData(
            db.invoices, {"_id": ObjectId(id_invoice)}, {"$set": update_data}
        )
        if not result:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )
        notification_data = {
            "id_invoice": ObjectId(id_invoice),
            "type": NotificationTypeData.PAYMENT_CONFIRM.value,
            "title": "Konfirmasi Pembayaran",
            "description": f"{exist_data.get('name', 'Pelanggan')} melakukan konfirmasi pembayaran",
            "is_read": 0,
            "created_at": GetCurrentDateTime(),
        }
        admin_user = await GetAggregateData(
            db.users,
            [
                {
                    "$match": {
                        "role": UserRole.OWNER,
                    }
                }
            ],
        )
        if len(admin_user) > 0:
            for user in admin_user:
                notification_data["id_user"] = ObjectId(user["_id"])
                await CreateOneData(db.notifications, notification_data.copy())

        return JSONResponse(
            content={"message": "Permintaan Konfirmasi Pembayaran Telah Dikirimkan"}
        )
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.get("/ipaymu/channel")
async def get_ipaymu_channel():
    try:
        timestamp = GetCurrentDateTime().strftime("%Y%m%d%H%M%S")
        body = {}

        data_body = json.dumps(body)
        data_body = json.dumps(body, separators=(",", ":"))
        encrypt_body = hashlib.sha256(data_body.encode()).hexdigest()
        string_to_sign = "{}:{}:{}:{}".format(
            "GET", IPAYMU_VA, encrypt_body, IPAYMU_API_TOKEN
        )
        signature = (
            hmac.new(IPAYMU_API_TOKEN.encode(), string_to_sign.encode(), hashlib.sha256)
            .hexdigest()
            .lower()
        )
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
            "signature": signature,
            "va": IPAYMU_VA,
            "timestamp": timestamp,
        }
        ipaymu_url = f"{IPAYMU_API_DOMAIN}/api/v2/payment-channels"
        response = requests.get(ipaymu_url, headers=headers, data=data_body, timeout=60)
        response = response.json()
        channel_options = []
        for item in response.get("Data", []):
            if item.get("Code") in ["cstore", "va"]:
                channel_options += item.get("Channels", [])

        return JSONResponse(content={"channel_options": channel_options})
    except Exception as e:
        raise HTTPException(
            status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE, "err_msg": str(e)}
        )


@router.post("/ipaymu/add/{id_invoice}")
async def create_ipaymu_payment(
    id_invoice: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        exist_invoice = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
        if not exist_invoice:
            raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

        customer_data = await GetOneData(
            db.customers,
            {"_id": ObjectId(exist_invoice["id_customer"])},
            {
                "name": 1,
                "email": 1,
                "phone_number": 1,
            },
        )
        if customer_data:
            exist_invoice["customer"] = customer_data

        timestamp = GetCurrentDateTime().strftime("%Y%m%d%H%M%S")
        body = {
            "product": ["Paket Langganan Amreta Net"],
            "qty": ["1"],
            "price": [exist_invoice.get("amount", 0)],
            "amount": exist_invoice.get("amount", 0),
            "returnUrl": IPAYMU_RETURN_URL,
            "notifyUrl": IPAYMU_CALLBACK_URL,
            "referenceId": exist_invoice.get("_id"),
            "buyerName": exist_invoice.get("customer", {}).get("name", ""),
            "buyerPhone": f"0{exist_invoice.get('customer', {}).get('phone_number', '')}",
            "buyerEmail": exist_invoice.get("customer", {}).get("email", ""),
        }

        data_body = json.dumps(body)
        data_body = json.dumps(body, separators=(",", ":"))
        encrypt_body = hashlib.sha256(data_body.encode()).hexdigest()
        string_to_sign = "{}:{}:{}:{}".format(
            "POST", IPAYMU_VA, encrypt_body, IPAYMU_API_TOKEN
        )
        signature = (
            hmac.new(IPAYMU_API_TOKEN.encode(), string_to_sign.encode(), hashlib.sha256)
            .hexdigest()
            .lower()
        )
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
            "signature": signature,
            "va": IPAYMU_VA,
            "timestamp": timestamp,
        }
        ipaymu_url = f"{IPAYMU_API_DOMAIN}/api/v2/payment"
        response = requests.post(
            ipaymu_url, headers=headers, data=data_body, timeout=60
        )
        response = response.json()

        payment_url = response.get("Data", {}).get("Url", None)
        return JSONResponse(content={"payment_url": payment_url})
    except Exception as e:
        await CreateOneData(
            db.logs_plugin,
            {
                "plugin": "Ipaymu",
                "created_at": GetCurrentDateTime(),
                "error_message": str(e),
            },
        )
        raise HTTPException(
            status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE, "err_msg": str(e)}
        )


@router.post("/ipaymu/callback")
async def ipaymu_payment_callback(
    request: Request,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail={"message": "Body is Not JSON"})

        body_str = body.decode("utf-8")
        if body_str.startswith("{"):
            callback_data = json.loads(body_str)
        else:
            parsed_data = urllib.parse.parse_qs(body_str)
            callback_data = {key: value[0] for key, value in parsed_data.items()}

        status_code = callback_data.get("status_code", "0")
        id_invoice = callback_data.get("reference_id", None)
        channel = callback_data.get("payment_channel", "")
        if status_code == "1" and id_invoice:
            invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
            if not invoice_data:
                pass

            result = await UpdateOneData(
                db.invoices,
                {"_id": ObjectId(id_invoice)},
                {
                    "$set": {
                        "status": InvoiceStatusData.PAID,
                        "payment.method": PaymentMethodData.TRANSFER.value,
                        "payment.paid_at": GetCurrentDateTime(),
                        "payment.description": f"Pembayaran Tagihan Periode {DateIDFormatter(str(invoice_data.get('due_date')))} (By IPaymu)",
                        "payment.confirmed_at": GetCurrentDateTime(),
                        "payment.confirmed_by": AUTOCONFIRM_USER_EMAIL,
                        "payment.channel": channel,
                        "owner_verified_status": InvoiceOwnerVerifiedStatusData.ACCEPTED.value,
                    }
                },
                upsert=True,
            )
            if not result:
                pass

            income_data = {
                "id_invoice": ObjectId(id_invoice),
                "nominal": invoice_data.get("amount", 0),
                "category": "BAYAR TAGIHAN",
                "description": f"Pembayaran Tagihan dengan Nomor Layanan {invoice_data.get('service_number', '-')} a/n {invoice_data.get('name', '-')}, Periode {DateIDFormatter(invoice_data.get('due_date'))}",
                "method": PaymentMethodData.TRANSFER.value,
                "date": GetCurrentDateTime(),
                "id_receiver": ObjectId(AUTOCONFIRM_USER_ID),
                "created_at": GetCurrentDateTime(),
            }
            await UpdateOneData(
                db.incomes,
                {"id_invoice": ObjectId(id_invoice)},
                {"$set": income_data},
                upsert=True,
            )

            asyncio.create_task(SendWhatsappPaymentSuccessMessage(db, [id_invoice]))
            asyncio.create_task(SendTelegramPaymentMessage(db, id_invoice))

            customer_data = await GetOneData(
                db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
            )
            if not customer_data:
                pass

            status = customer_data.get("status", None)
            if (
                status != CustomerStatusData.ACTIVE
                and status != CustomerStatusData.FREE
            ):
                await UpdateOneData(
                    db.customers,
                    {"_id": ObjectId(invoice_data["id_customer"])},
                    {"$set": {"status": CustomerStatusData.ACTIVE.value}},
                )
                await ActivateMikrotikPPPSecret(db, customer_data, False)

            await CheckMitraFee(db, customer_data, id_invoice)

            notification_data = {
                "id_user": ObjectId(customer_data["id_user"]),
                "title": "Tagihan Telah Dibayar",
                "description": f"Tagihan anda senilai Rp{ThousandSeparator(invoice_data.get('amount', 0))} telah dkonfirmasi!",
                "type": NotificationTypeData.OTHER.value,
                "is_read": 0,
                "created_at": GetCurrentDateTime(),
            }
            await CreateOneData(db.notifications, notification_data)

        return JSONResponse(content={"message": "Callback Diterima"})
    except Exception as e:
        await CreateOneData(
            db.logs_plugin,
            {
                "plugin": "Ipaymu",
                "created_at": GetCurrentDateTime(),
                "error_message": str(e),
            },
        )
        raise HTTPException(
            status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE, "err_msg": str(e)}
        )
