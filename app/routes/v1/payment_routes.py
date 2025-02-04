import base64
import json
import time
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
from app.models.invoices import InvoiceStatusData
from app.models.payments import (
    PaymentPayOffData,
    RequestConfirmData,
)
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
from datetime import timedelta
from app.modules.telegram_message import SendTelegramPaymentMessage

load_dotenv()

# moota config
MOOTA_API_TOKEN = os.getenv("MOOTA_API_TOKEN")
MOOTA_BANK_ACCOUNT_ID = os.getenv("MOOTA_BANK_ACCOUNT_ID")
# duitku config
DUITKU_API_DOMAIN = os.getenv("DUITKU_API_DOMAIN")
DUITKU_MERCHANT_CODE = os.getenv("DUITKU_MERCHANT_CODE")
DUITKU_API_TOKEN = os.getenv("DUITKU_API_TOKEN")
DUITKU_CALLBACK_URL = os.getenv("DUITKU_CALLBACK_URL")
DUITKU_RETURN_URL = os.getenv("DUITKU_RETURN_URL")

router = APIRouter(prefix="/payment", tags=["Payments"])


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
    update_data = {
        "status": InvoiceStatusData.PAID,
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
        "date": GetCurrentDateTime(),
        "id_receiver": ObjectId(current_user.id),
        "created_at": GetCurrentDateTime(),
    }
    await UpdateOneData(
        db.incomes, {"id_invoice": ObjectId(id)}, {"$set": income_data}, upsert=True
    )

    await SendWhatsappPaymentSuccessMessage(db, id)
    await SendTelegramPaymentMessage(db, id)

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

    notification_data = {
        "id_user": ObjectId(customer_data["id_user"]),
        "title": "Tagihan Telah Dibayar",
        "description": f"Tagihan anda senilai Rp{ThousandSeparator(invoice_data.get('amount', 0))} telah dkonfirmasi!",
        "type": NotificationTypeData.OTHER.value,
        "is_read": 0,
        "created_at": GetCurrentDateTime(),
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

        result = await UpdateOneData(
            db.invoices,
            {"_id": ObjectId(id)},
            {
                "$set": {
                    "status": InvoiceStatusData.PAID,
                    "payment.confirmed_by": current_user.email,
                    "payment.confirmed_at": GetCurrentDateTime(),
                }
            },
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

        await SendWhatsappPaymentSuccessMessage(db, id)
        await SendTelegramPaymentMessage(db, id)

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


@router.get("/moota/mutation")
async def get_moota_mutation(amount: int = 0):
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {MOOTA_API_TOKEN}",
    }
    start_date = (GetCurrentDateTime() - timedelta(days=3)).strftime("%Y-%m-%d")
    end_date = GetCurrentDateTime().strftime("%Y-%m-%d")
    url = f"https://app.moota.co/api/v2/mutation?amount={amount}&start_date={start_date}&end_date={end_date}"
    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except requests.exceptions.RequestException as e:
        return str(e)


@router.get("/moota/auto-confirm")
async def auto_confirm_moota_invoice(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    confirmed = 0
    duplicated = 0
    query = {"status": {"$in": ["UNPAID", "PENDING"]}}
    invoice_data, _ = await GetManyData(db.invoices, [{"$match": query}])
    for invoice in invoice_data:
        amount = invoice.get("amount", 0)
        print("check amount:", amount)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {MOOTA_API_TOKEN}",
        }
        start_date = (GetCurrentDateTime() - timedelta(days=3)).strftime("%Y-%m-%d")
        end_date = GetCurrentDateTime().strftime("%Y-%m-%d")
        url = f"https://app.moota.co/api/v2/mutation?amount={amount}&start_date={start_date}&end_date={end_date}"
        try:
            response = requests.get(url, headers=headers)
            response = response.json()
            print(response)
            result = response.get("data", [])
            if len(result) == 1:
                confirm_data = {
                    "status": "PAID",
                    "payment.method": PaymentMethodData.TRANSFER.value,
                    "payment.paid_at": GetCurrentDateTime(),
                    "payment.confirmed_at": GetCurrentDateTime(),
                    "payment.confirmed_by": "moota@gmail.com",
                }
                await UpdateOneData(
                    db.invoices,
                    {"_id": ObjectId(invoice["_id"])},
                    {"$set": confirm_data},
                )
                confirmed += 1
                income_data = {
                    "id_invoice": ObjectId(id),
                    "nominal": invoice.get("amount", 0),
                    "category": "BAYAR TAGIHAN",
                    "description": f"Pembayaran Tagihan dengan Nomor Layanan {invoice.get('service_number', '-')} a/n {invoice.get('name', '-')}, Periode {DateIDFormatter(invoice.get('due_date'))}",
                    "method": confirm_data["payment.method"],
                    "date": confirm_data["payment.paid_at"],
                    "created_at": GetCurrentDateTime(),
                }
                await UpdateOneData(
                    db.incomes,
                    {"id_invoice": ObjectId(invoice["_id"])},
                    {"$set": income_data},
                    upsert=True,
                )

                # update customer status
                await UpdateOneData(
                    db.customers,
                    {"_id": ObjectId(invoice["id_customer"])},
                    {"$set": {"status": CustomerStatusData.ACTIVE.value}},
                )
                customer_data = await GetOneData(
                    db.customers, {"_id": ObjectId(invoice["id_customer"])}
                )
                if customer_data:
                    await ActivateMikrotikPPPSecret(db, customer_data, False)

                await SendWhatsappPaymentSuccessMessage(db, invoice["_id"])
            elif len(result) > 1:
                await UpdateOneData(
                    db.invoices,
                    {"_id": ObjectId(invoice["_id"])},
                    {"$set": {"status": "PENDING"}},
                )
                duplicated += 1
        except requests.exceptions.RequestException as e:
            print(f"Error {str(e)}")

    print(f"Confirmed: {confirmed}, Duplicate Amount: {duplicated}")
    return JSONResponse(content={"message": "Auto Confirmed Telah Dijalankan!"})


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
                        "role": UserRole.ADMIN,
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
        print(e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.post("/virtual-account/add/{id_invoice}")
async def create_virtual_account_payment(
    id_invoice: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
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

    payload = {
        "paymentAmount": exist_invoice.get("amount", 0),
        "merchantOrderId": exist_invoice["_id"],
        "productDetails": "Pembayaran Paket Internet",
        "additionalParam": "",
        "merchantUserInfo": "",
        "customerVaName": exist_invoice.get("customer", {}).get("name", ""),
        "email": exist_invoice.get("customer", {}).get("email", ""),
        "phoneNumber": f"0{exist_invoice.get('customer', {}).get('phone_number', '')}",
        "callbackUrl": DUITKU_CALLBACK_URL,
        "returnUrl": DUITKU_RETURN_URL,
    }
    url = f"{DUITKU_API_DOMAIN}/api/merchant/createInvoice"

    timestamp = str(int(time.time() * 1000))
    signature_string = f"{DUITKU_MERCHANT_CODE}{timestamp}{DUITKU_API_TOKEN}"
    signature = hashlib.sha256(signature_string.encode()).hexdigest()

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-duitku-signature": signature,
        "x-duitku-timestamp": timestamp,
        "x-duitku-merchantcode": DUITKU_MERCHANT_CODE,
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response = response.json()
        return JSONResponse(content=response)
    except requests.exceptions.RequestException:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.post("/virtual-account/callback")
async def virtual_account_callback(
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

        if callback_data.get("resultCode") == "00":
            id_invoice = callback_data.get("merchantOrderId")
            if id_invoice:
                invoice_data = await GetOneData(
                    db.invoices, {"_id": ObjectId(id_invoice)}
                )
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
                            "payment.description": f"Pembayaran Tagihan Periode {DateIDFormatter(str(invoice_data.get('due_date')))} (By Duitku)",
                            "payment.confirmed_at": GetCurrentDateTime(),
                            "payment.confirmed_by": "duitku@gmail.com",
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
                    "id_receiver": ObjectId("67a1c07d327cb97bbe41ea8a"),
                    "created_at": GetCurrentDateTime(),
                }
                await UpdateOneData(
                    db.incomes,
                    {"id_invoice": ObjectId(id_invoice)},
                    {"$set": income_data},
                    upsert=True,
                )

                await SendWhatsappPaymentSuccessMessage(db, id_invoice)
                await SendTelegramPaymentMessage(db, id_invoice)

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

                notification_data = {
                    "id_user": ObjectId(customer_data["id_user"]),
                    "title": "Tagihan Telah Dibayar",
                    "description": f"Tagihan anda senilai Rp{ThousandSeparator(invoice_data.get('amount', 0))} telah dkonfirmasi!",
                    "type": NotificationTypeData.OTHER.value,
                    "is_read": 0,
                    "created_at": GetCurrentDateTime(),
                }
                await CreateOneData(db.notifications, notification_data)

        return callback_data
    except Exception as e:
        print("Error processing callback:", e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})
