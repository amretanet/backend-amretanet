import asyncio
from datetime import timedelta
from bson import ObjectId
from app.models.customers import CustomerStatusData
from app.modules.database import ConnectToMongoDB, DisconnectMongoDB, GetAmretaDatabase
from app.modules.crud_operations import GetManyData, GetOneData, UpdateOneData
from app.modules.generals import DateIDFormatter, GetCurrentDateTime
from app.models.payments import PaymentMethodData
from app.modules.mikrotik import ActivateMikrotikPPPSecret
from app.modules.whatsapp_message import SendWhatsappPaymentSuccessMessage
from app.routes.v1.invoice_routes import CheckMitraFee
import requests
from app.modules.telegram_message import SendTelegramPaymentMessage
from dotenv import load_dotenv
import os

load_dotenv()

AUTOCONFIRM_USER_ID = os.getenv("AUTOCONFIRM_USER_ID")
AUTOCONFIRM_USER_EMAIL = os.getenv("AUTOCONFIRM_USER_EMAIL")

MOOTA_API_TOKEN = os.getenv("MOOTA_API_TOKEN")
MOOTA_BANK_ACCOUNT_ID = os.getenv("MOOTA_BANK_ACCOUNT_ID")


async def main():
    start_time = GetCurrentDateTime()
    await ConnectToMongoDB()
    db = await GetAmretaDatabase()

    confirmed = 0
    duplicated = 0

    pipeline = [
        {
            "$match": {
                "status": {"$in": ["UNPAID", "PENDING"]},
                "due_date": {
                    "$gte": GetCurrentDateTime() - timedelta(days=5),
                    "$lte": GetCurrentDateTime() + timedelta(days=5),
                },
            }
        }
    ]
    success_invoice_ids = []
    invoices, _ = await GetManyData(db.invoices, pipeline)
    for invoice in invoices:
        print("=" * 100)
        amount = invoice.get("amount", 0)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {MOOTA_API_TOKEN}",
        }
        start_date = (GetCurrentDateTime() - timedelta(days=3)).strftime("%Y-%m-%d")
        end_date = GetCurrentDateTime().strftime("%Y-%m-%d")
        print(f"Check mutation {start_date} - {end_date}")
        print(f"ID Invoice: {invoice.get('_id')}")
        print(f"Amount : {amount}")
        url = f"https://app.moota.co/api/v2/mutation?amount={amount}&start_date={start_date}&end_date={end_date}"
        try:
            response = requests.get(url, headers=headers)
            response = response.json()
            result = response.get("data", [])
            if len(result) == 0:
                print(f"Mutation is Not Available : {result}")
            elif len(result) == 1:
                print(f"Mutation is Available : {result}")
                confirm_data = {
                    "status": "PAID",
                    "payment.method": PaymentMethodData.TRANSFER.value,
                    "payment.paid_at": GetCurrentDateTime(),
                    "payment.description": f"Pembayaran Tagihan Periode {DateIDFormatter(str(invoice.get('due_date')))} (By Moota)",
                    "payment.confirmed_at": GetCurrentDateTime(),
                    "payment.confirmed_by": AUTOCONFIRM_USER_EMAIL,
                }
                await UpdateOneData(
                    db.invoices, {"_id": invoice["_id"]}, {"$set": confirm_data}
                )
                confirmed += 1
                income_data = {
                    "id_invoice": invoice["_id"],
                    "nominal": invoice.get("amount", 0),
                    "category": "BAYAR TAGIHAN",
                    "description": f"Pembayaran Tagihan dengan Nomor Layanan {invoice.get('service_number', '-')} a/n {invoice.get('name', '-')}, Periode {DateIDFormatter(str(invoice.get('due_date')))}",
                    "method": confirm_data["payment.method"],
                    "date": confirm_data["payment.paid_at"],
                    "id_receiver": ObjectId(AUTOCONFIRM_USER_ID),
                    "created_at": GetCurrentDateTime(),
                }
                await UpdateOneData(
                    db.incomes,
                    {"id_invoice": invoice["_id"]},
                    {"$set": income_data},
                    upsert=True,
                )
                await UpdateOneData(
                    db.customers,
                    {"_id": invoice["id_customer"]},
                    {"$set": {"status": CustomerStatusData.ACTIVE.value}},
                )
                customer_data = await GetOneData(
                    db.customers, {"_id": invoice["id_customer"]}
                )
                if customer_data:
                    await ActivateMikrotikPPPSecret(db, customer_data, False)
                    await CheckMitraFee(db, customer_data, invoice["_id"])

                success_invoice_ids.append(invoice["_id"])
                await SendTelegramPaymentMessage(db, id)
            elif len(result) > 1:
                print(f"Mutation is Duplicated : {result}")
                duplicated += 1

            print("=" * 100)
        except Exception as e:
            print(str(e))

    if len(success_invoice_ids) > 0:
        await SendWhatsappPaymentSuccessMessage(db, success_invoice_ids)

    await DisconnectMongoDB()
    end_time = GetCurrentDateTime()
    execution_time = end_time - start_time
    print(f"Confirmed: {confirmed}, Duplicate Amount: {duplicated}")
    print(f"Execution Time : {execution_time}")


if __name__ == "__main__":
    asyncio.run(main())
