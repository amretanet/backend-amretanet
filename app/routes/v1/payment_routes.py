import base64
import json
from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Request,
)
from app.models.notifications import NotificationTypeData
from app.models.invoices import InvoiceStatusData
from app.models.payments import (
    PaymentPayOffData,
    PaymentVAInsertData,
    RequestConfirmData,
)
from app.models.customers import CustomerStatusData
from app.modules.response_message import NOT_FOUND_MESSAGE, SYSTEM_ERROR_MESSAGE
from fastapi.responses import JSONResponse
from app.models.users import UserData, UserRole
from app.modules.generals import DateIDFormatter, GetCurrentDateTime
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
import hmac
import os
from datetime import timedelta
from app.modules.telegram_message import SendTelegramPaymentMessage

load_dotenv()

# moota config
MOOTA_API_TOKEN = os.getenv("MOOTA_API_TOKEN")
MOOTA_BANK_ACCOUNT_ID = os.getenv("MOOTA_BANK_ACCOUNT_ID")
# tripay config
TRIPAY_API_TOKEN = os.getenv("TRIPAY_API_TOKEN")
TRIPAY_PRIVATE_KEY = os.getenv("TRIPAY_PRIVATE_KEY")
TRIPAY_MERCHANT_CODE = os.getenv("TRIPAY_MERCHANT_CODE")

router = APIRouter(prefix="/payment", tags=["Payments"])


@router.get("/channel")
async def get_payment_channel(
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {TRIPAY_API_TOKEN}",
    }
    url = "https://tripay.co.id/api/merchant/payment-channel"

    channel_options = []
    return channel_options
    # try:
    #     response = requests.get(url, headers=headers, timeout=5)
    #     response = response.json()
    #     if response["success"]:
    #         channel_options = response["data"]

    #     return channel_options
    # except requests.exceptions.RequestException:
    #     return channel_options


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

    return JSONResponse(content={"message": "Pembayaran Telah Dikonfirmasi!"})


@router.get("/moota/mutation")
async def get_moota_mutation(amount: int = None):
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {MOOTA_API_TOKEN}",
    }
    url = "https://app.moota.co/api/v2/mutation?amount=170000"
    # if amount is not None:

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
            result = response.get("data", [])
            if len(result) == 1:
                await UpdateOneData(
                    db.invoices,
                    {"_id": ObjectId(invoice["_id"])},
                    {
                        "$set": {
                            "status": "PAID",
                            "payment.method": PaymentMethodData.TRANSFER.value,
                            "payment.paid_at": GetCurrentDateTime(),
                        }
                    },
                )
                confirmed += 1

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
                await CreateOneData(db.notifications, notification_data)

        return JSONResponse(
            content={"message": "Permintaan Konfirmasi Pembayaran Telah Dikirimkan"}
        )
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})


@router.post("/virtual-account/add")
async def create_virtual_account_payment(
    data: PaymentVAInsertData = Body(..., embed=True),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)

    exist_invoice = await GetOneData(
        db.invoices, {"_id": ObjectId(payload["id_invoice"])}
    )
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

    merchant_ref = exist_invoice["_id"]
    amount = exist_invoice["amount"]

    sign_str = "{}{}{}".format(TRIPAY_MERCHANT_CODE, merchant_ref, amount)
    signature = hmac.new(
        bytes(TRIPAY_PRIVATE_KEY, "latin-1"), bytes(sign_str, "latin-1"), hashlib.sha256
    ).hexdigest()

    tripay_payload = {
        "method": payload["method"],
        "merchant_ref": merchant_ref,
        "amount": amount,
        "customer_name": exist_invoice.get("name", "-"),
        "customer_email": exist_invoice.get("customer", "-").get("email", "-"),
        "customer_phone": exist_invoice.get("customer", "-").get("phone_number", "-"),
        "order_items": [
            {
                "name": f"Pembayaran Layanan Amreta Net {exist_invoice.get('service_number', '')}",
                "price": amount,
                "quantity": 1,
            },
        ],
        "signature": signature,
    }
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {TRIPAY_API_TOKEN}",
    }

    url = "https://tripay.co.id/api/transaction/create"

    try:
        response = requests.post(url, json=tripay_payload, headers=headers)
        response = response.json()
        response = response.get("data", None)
        if response:
            update_data = {
                "status": "UNPAID",
                "payment": {
                    "reference": response["reference"],
                    "name": response["payment_name"],
                    "method": response["payment_method"],
                    "created_at": GetCurrentDateTime(),
                },
            }
            await UpdateOneData(
                db.invoices,
                {"_id": ObjectId(payload["id_invoice"])},
                {"$set": update_data},
            )
            return response

        return None
    except requests.exceptions.RequestException:
        return None


@router.post("/virtual-account/callback")
async def virtual_account_callback(
    request: Request,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    try:
        # get callback signature
        callback_signature = request.headers.get("x-callback-signature")
        if not callback_signature:
            raise HTTPException(status_code=400, detail="Signature not found")

        body = await request.body()
        callback_data = json.loads(body)

        # verify signature
        json_data = await request.json()
        json_string = json.dumps(json_data, separators=(",", ":"))

        # create signature
        signature = hmac.new(
            bytes(TRIPAY_PRIVATE_KEY, "latin-1"),
            bytes(json_string, "latin-1"),
            hashlib.sha256,
        ).hexdigest()

        if callback_signature != signature:
            raise HTTPException(status_code=403, detail="Invalid signature")

        # status = callback_data.get("status", None)
        # merchant_ref = callback_data.get("merchant_ref", None)

        # if status == "PAID" and merchant_ref:
        #     UpdateOneData(db.invoice,{"_id":ObjectId(merchant_ref)},{"$set"})

        print(callback_data)

        return JSONResponse(content={"success": True})
    except Exception as e:
        print("error", e)
        return JSONResponse(content={"Signature Not Found!"})
