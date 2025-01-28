import os
from urllib.parse import urlencode
from bson import ObjectId
import requests
from app.models.tickets import TicketTypeData
from app.modules.generals import GetCurrentDateTime, ThousandSeparator, DateIDFormatter
from app.modules.crud_operations import CreateOneData, GetAggregateData, GetOneData
from app.models.notifications import NotificationTypeData
from app.models.users import UserRole
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_INSTALLATION_THREAD_ID = os.getenv("TELEGRAM_INSTALLATION_THREAD_ID")
TELEGRAM_MAINTENANCE_THREAD_ID = os.getenv("TELEGRAM_MAINTENANCE_THREAD_ID")
TELEGRAM_PAYMENT_THREAD_ID = os.getenv("TELEGRAM_PAYMENT_THREAD_ID")


async def CreateTelegramErrorNotification(db, description: str):
    notification_data = {
        "title": "Telegram Message Error",
        "description": description,
        "type": NotificationTypeData.SYSTEM_ERROR.value,
        "is_read": 0,
        "created_at": GetCurrentDateTime(),
    }
    admin_user = await GetAggregateData(
        db.users, [{"$match": {"role": UserRole.ADMIN.value}}]
    )
    for user in admin_user:
        notification_data["id_user"] = ObjectId(user["_id"])
        await CreateOneData(db.notifications, notification_data.copy())


async def SendTelegramImage(image_url: list, thread_id):
    media_list = []
    for url in image_url:
        media_list.append(
            {
                "type": "photo",
                "media": url,
            }
        )
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": thread_id,
        "media": media_list,
        "caption": "Bukti Pengerjaan",
        "background": True,
    }
    telegram_api_url = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMediaGroup"
    )
    response = requests.post(telegram_api_url, json=data)
    print(response.json())


async def SendTelegramTicketOpenMessage(db, id_ticket: str):
    try:
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
                {
                    "name": 1,
                    "service_number": 1,
                    "pppoe_username": 1,
                    "pppoe_password": 1,
                    "location": 1,
                    "phone_number": 1,
                },
            )
            if customer:
                ticket_data["customer"] = customer
                SHORTCUT_BUTTON.append(
                    {
                        "text": "📞Telp Pelanggan",
                        "url": f"https://wa.me/62{customer.get('phone_number')}",
                    },
                )
                SHORTCUT_BUTTON.append(
                    {
                        "text": "📍Cek Lokasi",
                        "url": f"https://www.google.com/maps?q={customer.get('location').get('latitude')},{customer.get('location').get('longitude')}",
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

        v_message = f"*Tiket OPEN - {ticket_data.get('title', '')}*\n\n"
        v_message += (
            f"🗓️ *{DateIDFormatter(ticket_data.get('created_at'), is_show_time=True)}*\n"
        )
        v_message += f"*Kode Tiket*: #{ticket_data.get('name', '-')}\n"
        if "assignee" in ticket_data:
            v_message += f"*Teknisi*: {ticket_data.get('assignee', '').get('name')}\n\n"
        if "customer" in ticket_data:
            v_message += (
                f"*Nama Pelanggan*: {ticket_data.get('customer', '').get('name')}\n"
            )
            v_message += f"*Nomor Layanan*: {ticket_data.get('customer', '').get('service_number')}\n"
            v_message += f"*Username PPPOE*: {ticket_data.get('customer', '').get('pppoe_username')}\n"
            v_message += f"*Password PPPOE*: {ticket_data.get('customer', '').get('pppoe_password')}\n"
            v_message += f"*Alamat*: {ticket_data.get('customer', '').get('location', '').get('address', '-')}\n"
        v_message += f"*Deskripsi*: {ticket_data.get('description', '')}\n"
        if "odc" in ticket_data:
            v_message += f"*ODC*: {ticket_data.get('odc', '').get('name')}\n"
        if "odp" in ticket_data:
            v_message += f"*ODP*: {ticket_data.get('odp', '').get('name')}"

        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "message_thread_id": TELEGRAM_INSTALLATION_THREAD_ID
            if ticket_data.get("type") == TicketTypeData.PSB.value
            else TELEGRAM_MAINTENANCE_THREAD_ID,
            "text": v_message,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": [SHORTCUT_BUTTON]},
        }
        telegram_api_url = (
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        )
        requests.post(telegram_api_url, json=data)
    except Exception as e:
        await CreateTelegramErrorNotification(db, str(e))


async def SendTelegramTicketClosedMessage(db, id_ticket: str):
    try:
        SHORTCUT_BUTTON = []
        IMAGE_EVIDENCE = []
        ticket_data = await GetOneData(db.tickets, {"_id": ObjectId(id_ticket)})
        if not ticket_data:
            return

        if "evidence" in ticket_data:
            if "odp_image_url" in ticket_data["evidence"]:
                IMAGE_EVIDENCE.append(ticket_data["evidence"]["odp_image_url"])
            if "ont_image_url" in ticket_data["evidence"]:
                IMAGE_EVIDENCE.append(ticket_data["evidence"]["ont_image_url"])
            if "serial_number_image_url" in ticket_data["evidence"]:
                IMAGE_EVIDENCE.append(
                    ticket_data["evidence"]["serial_number_image_url"]
                )
            if "house_image_url" in ticket_data["evidence"]:
                IMAGE_EVIDENCE.append(ticket_data["evidence"]["house_image_url"])
            if "ont_position_image_url" in ticket_data["evidence"]:
                IMAGE_EVIDENCE.append(ticket_data["evidence"]["ont_position_image_url"])
            if "customer_image_url" in ticket_data["evidence"]:
                IMAGE_EVIDENCE.append(ticket_data["evidence"]["customer_image_url"])
            if "other_image_url" in ticket_data["evidence"]:
                IMAGE_EVIDENCE.append(ticket_data["evidence"]["other_image_url"])

        assignee = await GetOneData(
            db.users,
            {"_id": ObjectId(ticket_data["id_assignee"])},
            {"name": 1, "phone_number": 1},
        )
        if assignee:
            ticket_data["assignee"] = assignee
            SHORTCUT_BUTTON.append(
                {
                    "text": "📞Telp Teknisi",
                    "url": f"https://wa.me/62{assignee.get('phone_number')}",
                },
            )

        if ticket_data["type"] != TicketTypeData.FOM.value:
            customer = await GetOneData(
                db.customers,
                {"id_user": ObjectId(ticket_data["id_reporter"])},
                {
                    "name": 1,
                    "service_number": 1,
                    "pppoe_username": 1,
                    "pppoe_password": 1,
                    "location": 1,
                    "phone_number": 1,
                },
            )
            if customer:
                ticket_data["customer"] = customer
                SHORTCUT_BUTTON.append(
                    {
                        "text": "📍Cek Lokasi",
                        "url": f"https://www.google.com/maps?q={customer.get('location').get('latitude')},{customer.get('location').get('longitude')}",
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

        v_message = f"*Tiket CLOSED - {ticket_data.get('title', '')}*\n\n"
        v_message += (
            f"🗓️ *{DateIDFormatter(ticket_data.get('created_at'), is_show_time=True)}*\n"
        )
        v_message += f"*Kode Tiket*: #{ticket_data.get('name', '-')}\n"
        if "assignee" in ticket_data:
            v_message += f"*Teknisi*: {ticket_data.get('assignee', '').get('name')}\n\n"
        if "customer" in ticket_data:
            v_message += (
                f"*Nama Pelanggan*: {ticket_data.get('customer', '').get('name')}\n"
            )
            v_message += f"*Nomor Layanan*: {ticket_data.get('customer', '').get('service_number')}\n"
            v_message += f"*Username PPPOE*: {ticket_data.get('customer', '').get('pppoe_username')}\n"
            v_message += f"*Password PPPOE*: {ticket_data.get('customer', '').get('pppoe_password')}\n"
            v_message += f"*Alamat*: {ticket_data.get('customer', '').get('location', '').get('address', '-')}\n"
        v_message += f"*Deskripsi*: {ticket_data.get('description', '')}\n"
        if ticket_data.get("odc"):
            v_message += f"*ODC*: {ticket_data.get('odc', '').get('name')}\n"
        if ticket_data.get("odp"):
            v_message += f"*ODP*: {ticket_data.get('odp', '').get('name')}\n"
        if ticket_data.get("re_odp"):
            v_message += f"*Redaman ODP*: {ticket_data.get('re_odp', '')}dB\n"
        if ticket_data.get("re_ont"):
            v_message += f"*Redaman ONT*: {ticket_data.get('re_ont', '')}dB\n"
        if ticket_data.get("cable"):
            v_message += f"*Kabel*: {ticket_data.get('cable', '')} Meter\n"
        if ticket_data.get("hardware"):
            v_message += f"*Perangkat*: {ticket_data.get('hardware', '')}\n"
        if ticket_data.get("serial_number"):
            v_message += f"*Serial Number*: {ticket_data.get('serial_number', '')}\n"
        if ticket_data.get("confirm_message"):
            v_message += f"*Pesan Konfirmasi*: {ticket_data.get('confirm_message', '')}"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "message_thread_id": TELEGRAM_INSTALLATION_THREAD_ID
            if ticket_data.get("type") == TicketTypeData.PSB.value
            else TELEGRAM_MAINTENANCE_THREAD_ID,
            "text": v_message,
            "parse_mode": "Markdown",
            "reply_markup": {"inline_keyboard": [SHORTCUT_BUTTON]},
        }
        telegram_api_url = (
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        )
        requests.post(telegram_api_url, json=data)
        await SendTelegramImage(IMAGE_EVIDENCE, data["message_thread_id"])
    except Exception as e:
        await CreateTelegramErrorNotification(db, str(e))


async def SendTelegramPaymentMessage(db, id_invoice):
    try:
        invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
        if not invoice_data:
            return

        v_message = "*Pembayaran Pelanggan*\n\n"
        v_message += f"*Nama*: {invoice_data.get('name', 'Pelanggan')}\n"
        v_message += f"*Nomor Layanan*: {invoice_data.get('service_number', '-')}\n"
        v_message += (
            f"*Tagihan*: Rp{ThousandSeparator(invoice_data.get('amount', 0))}\n"
        )
        v_message += f"*Periode*: {DateIDFormatter(invoice_data.get('due_date'))}\n"
        v_message += f"*Tanggal Pembayaran*: {DateIDFormatter(invoice_data.get('payment').get('paid_at'))}\n"
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
        await CreateTelegramErrorNotification(db, str(e))
