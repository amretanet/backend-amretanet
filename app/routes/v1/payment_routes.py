import json
from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Request,
)
from app.models.payments import PaymentInsertData
from app.modules.response_message import NOT_FOUND_MESSAGE
from fastapi.responses import JSONResponse
from app.models.users import UserData
from app.modules.generals import GetCurrentDateTime
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import (
    CreateOneData,
    GetManyData,
    GetOneData,
    UpdateManyData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
import requests
from dotenv import load_dotenv
import hashlib
import hmac
import os

load_dotenv()

# moota config
MOOTA_API_TOKEN = os.getenv("MOOTA_API_TOKEN")
MOOTA_BANK_ACCOUNT_ID = os.getenv("MOOTA_BANK_ACCOUNT_ID")
# tripay
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
    try:
        response = requests.get(url, headers=headers)
        response = response.json()
        if response["success"]:
            channel_options = response["data"]

        return channel_options
    except requests.exceptions.RequestException:
        return channel_options


@router.post("/add")
async def create_payment(
    data: PaymentInsertData = Body(..., embed=True),
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
                "name": f"Pembayaran Layanan Amreta Net {exist_invoice.get('service_number','')}",
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


@router.post("/tripay/callback")
async def tripay_callback(
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

        status = callback_data.get("status", None)
        merchant_ref = callback_data.get("merchant_ref", None)

        # if status == "PAID" and merchant_ref:
        #     UpdateOneData(db.invoice,{"_id":ObjectId(merchant_ref)},{"$set"})

        print(callback_data)

        return JSONResponse(content={"success": True})
    except Exception:
        return JSONResponse(content={"Signature Not Found!"})
