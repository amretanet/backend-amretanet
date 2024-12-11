from io import BytesIO
from urllib.parse import urlencode, urljoin
from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from app.models.generals import Pagination
from app.models.router import RouterInsertData
from app.models.users import UserData
from app.modules.crud_operations import (
    CreateOneData,
    DeleteManyData,
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.pdf import CreateInvoicePDF, CreateInvoiceThermal
from app.modules.moota import (
    CreateMootaMutation,
    GetMootaMutationTracking,
    GetDetailMootaMutation,
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
import os
from dotenv import load_dotenv
import requests
from urllib.request import Request, urlopen
from fpdf import FPDF
from PIL import Image

load_dotenv()

MOOTA_API_TOKEN = os.getenv("MOOTA_API_TOKEN")


router = APIRouter(prefix="/invoice", tags=["Invoice"])


@router.get("")
async def get_invoice(
    key: str = None,
    page: int = 1,
    items: int = 1,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
        ]

    pipeline = [{"$match": query}, {"$sort": {"name": 1}}]

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


@router.get("/generate")
async def auto_generate_invoice(
    id_customer: str = None,
    is_send_whatsapp: bool = True,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    pipeline = []
    query = {}
    if id_customer:
        query["_id"] = ObjectId(id_customer)

    # add filter query
    pipeline.append({"$match": query})

    # add join id package query
    pipeline.append(
        {
            "$lookup": {
                "from": "packages",
                "localField": "id_package",
                "foreignField": "_id",
                "pipeline": [
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
                "localField": "id_add_on_package",
                "foreignField": "_id",
                "pipeline": [
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
                "package": 1,
                "package_amount": 1,
                "add_on_packages": 1,
                "add_on_package_amount": 1,
                "amount": 1,
            }
        }
    )

    customer_data, _ = await GetManyData(db.customers, pipeline)
    if len(customer_data) == 0:
        return ""

    whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
    API_URL = urljoin(whatsapp_bot.get("url_gateway", ""), "/send-message")
    API_TOKEN = whatsapp_bot.get("api_key", None)
    invoice_exist = 0
    invoice_created = 0
    for customer in customer_data:
        query = {
            "service_number": customer["service_number"],
            "month": GetCurrentDateTime().strftime("%m"),
            "year": GetCurrentDateTime().strftime("%Y"),
        }
        exist_invoice = await GetOneData(db.invoices, query)
        if exist_invoice:
            invoice_exist += 1
            continue

        unique_code = 0
        last_unique_code = await GetOneData(
            db.configurations, {"type": "INVOICE_UNIQUE_CODE"}
        )
        if last_unique_code:
            unique_code = int(last_unique_code["value"])

        current_unique_code = unique_code + 1
        final_amount = customer["amount"] + current_unique_code
        invoice_data = {
            "id_customer": ObjectId(customer["_id"]),
            "name": customer["name"],
            "service_number": customer["service_number"],
            "package": customer["package"],
            "due_date": f"{GetCurrentDateTime().strftime('%Y-%m')}-{customer['due_date']} 00:00:00",
            "add_on_packages": customer["add_on_packages"],
            "month": GetCurrentDateTime().strftime("%m"),
            "year": GetCurrentDateTime().strftime("%Y"),
            "status": "UNPAID",
            "package_amount": customer["package_amount"],
            "add_on_package_amount": customer["add_on_package_amount"],
            "unique_code": current_unique_code,
            "amount": final_amount,
            "created_at": GetCurrentDateTime(),
        }

        await CreateOneData(db.invoices, invoice_data)
        await UpdateOneData(
            db.configurations,
            {"type": "INVOICE_UNIQUE_CODE"},
            {"$set": {"value": current_unique_code}},
        )
        if API_TOKEN and is_send_whatsapp:
            params = {
                "api_key": API_TOKEN,
                "sender": f"62{whatsapp_bot['bot_number']}",
                "number": "6281218030424",
                "message": "Berikut Tagihan Ada : Rp.120000",
                "is_html": True,
            }
            final_url = f"{API_URL}?{urlencode(params)}"
            requests.post(final_url, json=params, timeout=10)

        invoice_created += 1

    return JSONResponse(
        content={
            "invoice_exist": invoice_exist,
            "invoice_created": invoice_created,
        }
    )


@router.get("/pdf/{id}")
async def print_invoice_pdf(
    id: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id)})
    if not invoice_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    customer_data = await GetOneData(
        db.customers,
        {"_id": ObjectId(invoice_data["id_customer"])},
        {"name": 1, "email": 1, "phone_number": 1, "address": "$location.address"},
    )
    if customer_data:
        invoice_data["customer"] = customer_data

    pdf_bytes = CreateInvoicePDF(invoice_data)
    file_name = (
        f'INVOICE-{invoice_data.get("name","")}-{GetCurrentDateTime().timestamp()}.pdf'
    )
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


@router.get("/thermal/{id}")
async def print_invoice_thermal(
    id: str,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id)})
    if not invoice_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    pdf_bytes = CreateInvoiceThermal(invoice_data)
    file_name = (
        f'INVOICE-{invoice_data.get("name","")}-{GetCurrentDateTime().timestamp()}.pdf'
    )
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )


@router.delete("/delete/{id}")
async def delete_invoice(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.invoices, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.invoices, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})


# @router.post("/get-moota")
# async def get_moota(
#     # current_user: UserData = Depends(GetCurrentUser),
#     db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
# ):
#     response = await GetMootaMutationTracking()
#     # response = await GetDetailMootaMutation("PYM-674c29337acd9-674c29337acdb")
#     return response


# @router.post("/add")
# async def create_invoice(
#     # current_user: UserData = Depends(GetCurrentUser),
#     db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
# ):
#     # Data payload
#     data = {
#         "bank_account_id": "KXajel1LzGo",
#         "customers": {
#             "name": "Jhon Doe",
#             "email": "test@gmail.com",
#             "phone": "0812871827371",
#         },
#         "items": [
#             {
#                 "name": "Air Mineral",
#                 "description": "Air berkualitas",
#                 "qty": 1,
#                 "price": 10000,
#             }
#         ],
#         "total": 10000,
#     }

#     # Headers
#     headers = {
#         "Accept": "application/json",
#         "Authorization": f"Bearer {MOOTA_API_TOKEN}",  # Token API Moota
#     }

#     # URL
#     # url = "https://app.moota.co/api/v2/mutation-tracking"
#     url = "https://app.moota.co/api/v2/mutation-tracking"

#     # Kirim request POST
#     try:
#         response = requests.post(url, json=data, headers=headers)
#         # response.raise_for_status()  # Periksa jika ada error HTTP
#         return response.json()  # Parsing response ke JSON
#     except requests.exceptions.RequestException as e:
#         return {"error": str(e)}  # Return error dalam format dictionary
