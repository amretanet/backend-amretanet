import asyncio
from bson import ObjectId
from app.models.customers import CustomerStatusData
from fastapi.responses import JSONResponse
from app.modules.generals import DateIDFormatter, GetCurrentDateTime, ThousandSeparator
from app.models.payments import PaymentMethodData
from app.modules.mikrotik import MikrotikConnection
from app.modules.whatsapp_message import MONTH_DICTIONARY
import requests
from librouteros.query import Key
from dotenv import load_dotenv
import os
from datetime import timedelta
from urllib.parse import urlencode
from pymongo import MongoClient

load_dotenv()

AMRETA_DB_URI = os.getenv("AMRETA_DB_URI")
AMRETA_DB_NAME = os.getenv("AMRETA_DB_NAME")
MOOTA_API_TOKEN = os.getenv("MOOTA_API_TOKEN")
MOOTA_BANK_ACCOUNT_ID = os.getenv("MOOTA_BANK_ACCOUNT_ID")
WHATSAPP_ADMIN_NUMBER = os.getenv("WHATSAPP_ADMIN_NUMBER")
WHATSAPP_BOT_NUMBER = os.getenv("WHATSAPP_BOT_NUMBER")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_INSTALLATION_THREAD_ID = os.getenv("TELEGRAM_INSTALLATION_THREAD_ID")
TELEGRAM_MAINTENANCE_THREAD_ID = os.getenv("TELEGRAM_MAINTENANCE_THREAD_ID")
TELEGRAM_PAYMENT_THREAD_ID = os.getenv("TELEGRAM_PAYMENT_THREAD_ID")


def get_database():
    client = MongoClient(AMRETA_DB_URI)
    return client[AMRETA_DB_NAME]


def get_mikrotik_router_by_id(id_router: str):
    db = get_database()
    host = None
    username = None
    password = None
    port = None
    router_data = db.router.find_one({"_id": ObjectId(id_router)})
    if router_data:
        host = router_data.get("ip_address", None)
        username = router_data.get("username", None)
        password = router_data.get("password", None)
        port = router_data.get("api_port", None)

    return host, username, password, port


def send_whatsapp_payment_success(id_invoice):
    db = get_database()
    try:
        invoice_data = db.invoices.find_one({"_id": id_invoice})
        whatsapp_bot = db.configurations.find_one({"type": "WHATSAPP_BOT"})
        whatsapp_message = db.configurations.find_one(
            {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
        )
        customer_data = db.customers.find_one({"_id": invoice_data["id_customer"]})
        if (
            not invoice_data
            or not whatsapp_bot
            or not whatsapp_message
            or not customer_data
        ):
            return

        message = whatsapp_message.get("paid", "")
        fields_to_replace = {
            "[nama_pelanggan]": customer_data.get("name", "-"),
            "[no_servis]": customer_data.get("service_number", "-"),
            "[nama_paket]": invoice_data.get("package", [])[0]["name"],
            "[jumlah_tagihan]": ThousandSeparator(invoice_data.get("amount", 0)),
            "[status]": "SUDAH DIBAYAR",
            "[hari]": GetCurrentDateTime().strftime("%d"),
            "[bulan]": MONTH_DICTIONARY[int(invoice_data.get("month"))],
            "[tahun]": GetCurrentDateTime().strftime("%Y"),
            "[metode_bayar]": invoice_data.get("payment", "-").get("method", "-"),
            "[thanks_wa]": whatsapp_message.get("advance", "").get(
                "thanks_message", ""
            ),
        }

        for key, value in fields_to_replace.items():
            try:
                message = message.replace(key, str(value))
            except Exception:
                message = message.replace(key, "-")

        params = {
            "api_key": WHATSAPP_API_KEY,
            "sender": WHATSAPP_BOT_NUMBER,
            "number": f"62{customer_data['phone_number']}",
            "message": message,
        }
        whatsapp_api_url = "https://wa7.amretanet.my.id/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)
    except Exception as e:
        print(str(e))


def send_telegram_payment_success(id_invoice):
    db = get_database()
    try:
        invoice_data = db.invoices.find_one({"_id": id_invoice})
        if not invoice_data:
            return

        v_message = "*Pembayaran Pelanggan*\n\n"
        v_message += f"*Nama*: {invoice_data.get('name', 'Pelanggan')}\n"
        v_message += f"*Nomor Layanan*: {invoice_data.get('service_number', '-')}\n"
        v_message += (
            f"*Tagihan*: Rp{ThousandSeparator(invoice_data.get('amount', 0))}\n"
        )
        v_message += (
            f"*Periode*: {DateIDFormatter(str(invoice_data.get('due_date')))}\n"
        )
        v_message += f"*Tanggal Pembayaran*: {DateIDFormatter(str(invoice_data.get('payment').get('paid_at')))}\n"
        v_message += (
            f"*Metode Pembayaran*: {invoice_data.get('payment').get('method')}\n"
        )
        if invoice_data.get("payment").get("method") in ["TRANSFER", "QRIS"]:
            v_message += (
                f"*Bukti Pembayaran*: {invoice_data.get('payment').get('image_url')}\n"
            )

        params = {
            "chat_id": TELEGRAM_CHAT_ID,
            "message_thread_id": TELEGRAM_PAYMENT_THREAD_ID,
            "text": v_message,
            "parse_mode": "Markdown",
        }
        telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?{urlencode(params)}"
        requests.get(telegram_api_url)

    except Exception as e:
        print(str(e))


def activate_mikrotik_ppp_secret(customer_data, disabled: bool = False):
    db = get_database()
    try:
        pppoe_username = customer_data.get("pppoe_username", None)
        pppoe_password = customer_data.get("pppoe_password", None)
        id_router = customer_data.get("id_router", None)

        # check router
        host, username, password, port = get_mikrotik_router_by_id(str(id_router))
        if not host:
            return False

        secret_data = []
        secret_id = None
        mikrotik = MikrotikConnection(host, username, password, port)
        name = Key("name")
        for row in mikrotik.path("/ppp/secret").select().where(name == pppoe_username):
            secret_data.append(row)

        # get specified secret
        secret_id = None
        if len(secret_data) > 0:
            secret_id = secret_data[0].get(".id", None)

        if secret_id:
            # update exist secret
            update_data = {
                ".id": secret_id,
                "disabled": disabled,
            }
            if pppoe_username:
                update_data["name"] = pppoe_username
            if pppoe_password:
                update_data["password"] = pppoe_password

            mikrotik.path("/ppp/secret").update(**update_data)
        else:
            # create new secret data
            package_data = db.packages.find_one(
                {"_id": customer_data.get("id_package", None)}
            )
            if not package_data:
                return False

            insert_data = {
                "name": str(pppoe_username),
                "password": str(pppoe_password),
                "service": "ppp",
                "profile": package_data.get("router_profile", "default"),
                "disabled": disabled,
                "comment": customer_data.get("name", "Undefined"),
            }
            mikrotik.path("/ppp/secret").add(**insert_data)

        if disabled:
            active_data = []
            for row in (
                mikrotik.path("/ppp/active").select().where(name == pppoe_username)
            ):
                active_data.append(row)

            if len(active_data) > 0:
                active_id = active_data[0].get(".id")
                mikrotik.path("/ppp/active").remove(active_id)
    except Exception:
        return False

    return True


async def main():
    start_time = GetCurrentDateTime()
    db = get_database()
    confirmed = 0
    duplicated = 0
    invoice_data = list(db.invoices.find({"status": {"$in": ["UNPAID", "PENDING"]}}))
    for invoice in invoice_data:
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
                    "payment.description": "Dikonfirmasi Oleh Moota",
                    "payment.confirmed_at": GetCurrentDateTime(),
                    "payment.confirmed_by": "moota@gmail.com",
                }
                db.invoices.update_one({"_id": invoice["_id"]}, {"$set": confirm_data})
                confirmed += 1
                income_data = {
                    "id_invoice": invoice["_id"],
                    "nominal": invoice.get("amount", 0),
                    "category": "BAYAR TAGIHAN",
                    "description": f"Pembayaran Tagihan dengan Nomor Layanan {invoice.get('service_number', '-')} a/n {invoice.get('name', '-')}, Periode {DateIDFormatter(str(invoice.get('due_date')))}",
                    "method": confirm_data["payment.method"],
                    "date": confirm_data["payment.paid_at"],
                    "id_receiver": ObjectId("679c82f005a1aae3d2b43520"),
                    "created_at": GetCurrentDateTime(),
                }
                db.incomes.update_one(
                    {"id_invoice": invoice["_id"]},
                    {"$set": income_data},
                    upsert=True,
                )

                # update customer status
                db.customers.update_one(
                    {"_id": invoice["id_customer"]},
                    {"$set": {"status": CustomerStatusData.ACTIVE.value}},
                )

                customer_data = db.customers.find_one({"_id": invoice["id_customer"]})
                if customer_data:
                    activate_mikrotik_ppp_secret(customer_data, False)

                send_whatsapp_payment_success(invoice["_id"])
                send_telegram_payment_success(invoice["_id"])
            elif len(result) > 1:
                print(f"Mutation is Duplicated : {result}")
                duplicated += 1
            print("=" * 100)
        except requests.exceptions.RequestException as e:
            print(f"Error {str(e)}")

    end_time = GetCurrentDateTime()
    execution_time = end_time - start_time
    print(f"Confirmed: {confirmed}, Duplicate Amount: {duplicated}")
    print(f"Execution Time : {execution_time}")
    return JSONResponse(content={"message": "Auto Confirmed Telah Dijalankan!"})


if __name__ == "__main__":
    asyncio.run(main())
