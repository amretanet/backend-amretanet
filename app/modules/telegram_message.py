import os
from urllib.parse import urlencode
from bson import ObjectId
import requests
from app.models.tickets import TicketTypeData
from app.modules.generals import ThousandSeparator, DateIDFormatter
from app.modules.crud_operations import GetOneData
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_INSTALATION_THREAD_ID = os.getenv("TELEGRAM_INSTALATION_THREAD_ID")
TELEGRAM_MAINTENANCE_THREAD_ID = os.getenv("TELEGRAM_MAINTENANCE_THREAD_ID")
TELEGRAM_PAYMENT_THREAD_ID = os.getenv("TELEGRAM_PAYMENT_THREAD_ID")


async def SendTelegramTicketOpenMessage(db, id_ticket: str):
    SHORTCUT_BUTTON = []
    ticket_data = await GetOneData(db.tickets, {"_id": ObjectId(id_ticket)})
    if not ticket_data:
        return

    assignee = await GetOneData(
        db.users,
        {"_id": ObjectId(ticket_data["id_assignee"])},
        {"name": 1, "phone_number": 1},
    )
    if assignee:
        ticket_data["assignee"] = assignee

    if ticket_data["type"] != TicketTypeData.FOM.value:
        customer = await GetOneData(
            db.customers,
            {"id_user": ObjectId(ticket_data["id_reporter"])},
            {"name": 1, "service_number": 1, "location": 1, "phone_number": 1},
        )
        if customer:
            ticket_data["customer"] = customer
            SHORTCUT_BUTTON.append(
                {
                    "text": "📞Telp Pelanggan",
                    "url": f'https://wa.me/62{customer.get("phone_number")}',
                },
            )
            SHORTCUT_BUTTON.append(
                {
                    "text": "📍Cek Lokasi",
                    "url": f'https://www.google.com/maps?q={customer.get("location").get("latitude")},{customer.get("location").get("longitude")}',
                },
            )

    if "id_odc" in ticket_data and ticket_data["id_odc"] is not None:
        odc = await GetOneData(db.odc, {"_id": ObjectId(ticket_data["id_odc"])})
        if odc:
            ticket_data["odc"] = odc
    if "id_odp" in ticket_data and ticket_data["id_odp"] is not None:
        odp = await GetOneData(db.odp, {"_id": ObjectId(ticket_data["id_odp"])})
        if odp:
            ticket_data["odp"] = odp

    v_message = f'*Tiket OPEN - {ticket_data.get("title","")}*\n\n'
    v_message += f'*Kode Tiket*: #{ticket_data.get("name","-")}\n'
    if "assignee" in ticket_data:
        v_message += f'*Teknisi*: {ticket_data.get("assignee","").get("name")}\n\n'
    if "customer" in ticket_data:
        v_message += f'*Nama Pelanggan*: {ticket_data.get("customer","").get("name")}\n'
        v_message += (
            f'*Nomor Layanan*: {ticket_data.get("customer","").get("service_number")}\n'
        )
        v_message += f'*Alamat*: {ticket_data.get("customer","").get("location","").get("address","-")}\n'
    if "odc" in ticket_data:
        v_message += f'*ODC*: {ticket_data.get("odc","").get("name")}\n'
    if "odp" in ticket_data:
        v_message += f'*ODP*: {ticket_data.get("odp","").get("name")}\n'
    v_message += f'*Deskripsi*: {ticket_data.get("description","")}\n'
    v_message += (
        f'\n\nWaktu: {DateIDFormatter(ticket_data.get("created_at"),is_show_time=True)}'
    )
    print(SHORTCUT_BUTTON)
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": TELEGRAM_MAINTENANCE_THREAD_ID,
        "text": v_message,
        "parse_mode": "Markdown",
        "reply_markup": {"inline_keyboard": [SHORTCUT_BUTTON]},
    }
    telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(telegram_api_url, json=data)
    print(response.json())


async def SendTelegramPaymentMessage(db, id_invoice):
    invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
    if not invoice_data:
        return

    v_message = "*Pembayaran Pelanggan*\n\n"
    v_message += f'*Nama*: {invoice_data.get("name","Pelanggan")}\n'
    v_message += f'*Nomor Layanan*: {invoice_data.get("service_number","-")}\n'
    v_message += f'*Tagihan*: Rp{ThousandSeparator(invoice_data.get("amount",0))}\n'
    v_message += f'*Periode*: {DateIDFormatter(invoice_data.get("due_date"))}\n'
    v_message += f'*Tanggal Pembayaran*: {DateIDFormatter(invoice_data.get("payment").get("paid_at"))}\n'
    v_message += f'*Metode Pembayaran*: {invoice_data.get("payment").get("method")}\n'
    if invoice_data.get("payment").get("method") in ["TRANSFER", "QRIS"]:
        v_message += (
            f"*Bukti Pembayaran*: {invoice_data.get("payment").get("image_url")}\n"
        )

    params = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": TELEGRAM_PAYMENT_THREAD_ID,
        "text": v_message,
        "parse_mode": "Markdown",
    }
    telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?{urlencode(params)}"
    requests.get(telegram_api_url)
