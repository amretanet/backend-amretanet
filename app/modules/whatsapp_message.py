from bson import ObjectId
import requests
from app.models.tickets import TicketTypeData
from app.modules.crud_operations import (
    CreateOneData,
    GetAggregateData,
    GetOneData,
    UpdateOneData,
)
from app.modules.generals import DateIDFormatter, GetCurrentDateTime, ThousandSeparator
import os
from app.models.notifications import NotificationTypeData
from app.models.users import UserRole
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_GATEWAY_URL = os.getenv("WHATSAPP_GATEWAY_URL")
WHATSAPP_ADMIN_NUMBER = os.getenv("WHATSAPP_ADMIN_NUMBER")
WHATSAPP_BOT_NUMBER = os.getenv("WHATSAPP_BOT_NUMBER")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY")
FRONTEND_DOMAIN = os.getenv("FRONTEND_DOMAIN")
MONTH_DICTIONARY = {
    1: "Januari",
    2: "Februari",
    3: "Maret",
    4: "April",
    5: "Mei",
    6: "Juni",
    7: "Juli",
    8: "Agustus",
    9: "September",
    10: "Oktober",
    11: "November",
    12: "Desember",
}


async def CreateWhatsappErrorNotification(db, description: str):
    notification_data = {
        "title": "Whatsapp Message Error",
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


def WhatsappMessageFormatter(title: str, body: str):
    formatted_message = f"*{title}*\n{body}"
    return formatted_message


async def SendWhatsappMessage(destination_number, message):
    params = {
        "api_key": WHATSAPP_API_KEY,
        "sender": WHATSAPP_BOT_NUMBER,
        "number": f"62{destination_number}",
        "message": message,
    }
    whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
    response = requests.post(whatsapp_api_url, json=params)
    return response


async def SendWhatsappCustomerRegisterMessage(db, id_customer):
    try:
        customer_data = await GetOneData(db.customers, {"_id": ObjectId(id_customer)})
        whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
        whatsapp_message = await GetOneData(
            db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
        )
        if not customer_data or not whatsapp_bot or not whatsapp_message:
            return
        package_data = await GetOneData(
            db.packages, {"_id": ObjectId(customer_data["id_package"])}
        )
        message = whatsapp_message.get("register", "")
        fields_to_replace = {
            "[nama_pelanggan]": customer_data.get("name", "-"),
            "[no_ktp]": customer_data.get("id_card", "").get("number", "-"),
            "[alamat]": customer_data.get("location", "").get("address", "-"),
            "[nama_paket]": package_data.get("name", "-"),
            "[harga]": ThousandSeparator(
                package_data.get("price", 0).get("regular", 0)
            ),
            "[tanggal_psb]": DateIDFormatter(customer_data.get("installed_at", "")),
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
        whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)
    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))


async def SendWhatsappCustomerActivatedMessage(db, id_customer):
    try:
        customer_data = await GetOneData(db.customers, {"_id": ObjectId(id_customer)})
        whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
        whatsapp_message = await GetOneData(
            db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
        )
        if not customer_data or not whatsapp_bot or not whatsapp_message:
            return

        message = whatsapp_message.get("activate", "")
        fields_to_replace = {
            "[nama_pelanggan]": customer_data.get("name", "-"),
            "[no_servis]": customer_data.get("service_number", "-"),
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
        whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)
    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))


async def SendWhatsappPaymentCreatedMessage(db, id_invoice):
    try:
        invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
        whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
        whatsapp_message = await GetOneData(
            db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
        )
        customer_data = await GetOneData(
            db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
        )
        if (
            not invoice_data
            or not whatsapp_bot
            or not whatsapp_message
            or not customer_data
        ):
            return

        message = whatsapp_message.get("billing", "")
        fields_to_replace = {
            "[nama_pelanggan]": customer_data.get("name", "-"),
            "[no_servis]": customer_data.get("service_number", "-"),
            "[nama_paket]": invoice_data.get("package", [])[0]["name"],
            "[jumlah_tagihan]": ThousandSeparator(invoice_data.get("amount", 0)),
            "[status]": "BELUM DIBAYAR",
            "[tgl_due_date]": customer_data.get("due_date", ""),
            "[bulan_tagihan]": MONTH_DICTIONARY[int(invoice_data.get("month"))],
            "[tahun_tagihan]": invoice_data.get("year"),
            "[link]": f"{FRONTEND_DOMAIN}/quick-payment?id={id_invoice}",
            "[footer_wa]": whatsapp_message.get("advance", "").get("footer", ""),
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
        whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)
        await UpdateOneData(
            db.invoices,
            {"_id": ObjectId(id_invoice)},
            {"$set": {"is_whatsapp_sended": True}},
        )
    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))


async def SendWhatsappPaymentReminderMessage(db, id_invoice):
    try:
        invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
        whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
        whatsapp_message = await GetOneData(
            db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
        )
        customer_data = await GetOneData(
            db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
        )
        if (
            not invoice_data
            or not whatsapp_bot
            or not whatsapp_message
            or not customer_data
        ):
            return

        message = whatsapp_message.get("reminder", "")
        fields_to_replace = {
            "[nama_pelanggan]": customer_data.get("name", "-"),
            "[jumlah_tagihan]": ThousandSeparator(invoice_data.get("amount", 0)),
            "[link]": f"{FRONTEND_DOMAIN}/quick-payment?id={id_invoice}",
            "[footer_wa]": whatsapp_message.get("advance", "").get("footer", ""),
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
        whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)
        await UpdateOneData(
            db.invoices,
            {"_id": ObjectId(id_invoice)},
            {"$set": {"is_whatsapp_reminder_sended": True}},
        )
    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))


async def SendWhatsappPaymentOverdueMessage(db, id_invoice):
    try:
        invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
        whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
        whatsapp_message = await GetOneData(
            db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
        )
        customer_data = await GetOneData(
            db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
        )
        if (
            not invoice_data
            or not whatsapp_bot
            or not whatsapp_message
            or not customer_data
        ):
            return

        message = whatsapp_message.get("overdue", "")
        fields_to_replace = {
            "[judul]": f"*{whatsapp_message.get('advance', '').get('header', '')}*",
            "[nama_pelanggan]": customer_data.get("name", "-"),
            "[no_servis]": customer_data.get("service_number", "-"),
            "[link]": f"{FRONTEND_DOMAIN}/quick-payment?id={id_invoice}",
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
        whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)
        await UpdateOneData(
            db.invoices,
            {"_id": ObjectId(id_invoice)},
            {"$set": {"is_whatsapp_overdue_sended": True}},
        )
    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))


async def SendWhatsappIsolirMessage(db, id_invoice):
    try:
        invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
        whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
        whatsapp_message = await GetOneData(
            db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
        )
        customer_data = await GetOneData(
            db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
        )
        if (
            not invoice_data
            or not whatsapp_bot
            or not whatsapp_message
            or not customer_data
        ):
            return

        message = whatsapp_message.get("isolir", "")
        fields_to_replace = {
            "[nama_pelanggan]": customer_data.get("name", "-"),
            "[jumlah_tagihan]": ThousandSeparator(invoice_data.get("amount", 0)),
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
        whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)
    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))


async def SendWhatsappPaymentSuccessMessage(db, id_invoice):
    try:
        invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
        whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
        whatsapp_message = await GetOneData(
            db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
        )
        customer_data = await GetOneData(
            db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
        )
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
        whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)
    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))


async def SendWhatsappTicketOpenMessage(
    db, id_ticket: str, is_only_assignee: bool = False
):
    try:
        PHONE_NUMBERS = []
        if not is_only_assignee:
            PHONE_NUMBERS.append(WHATSAPP_ADMIN_NUMBER)
        ticket_data = await GetOneData(db.tickets, {"_id": ObjectId(id_ticket)})
        if not ticket_data:
            return

        assignee = await GetOneData(
            db.users,
            {"_id": ObjectId(ticket_data["id_assignee"])},
            {"name": 1, "phone_number": 1},
        )
        if assignee:
            PHONE_NUMBERS.append(assignee.get("phone_number"))
            ticket_data["assignee"] = assignee

        if ticket_data["type"] != TicketTypeData.FOM.value:
            customer = await GetOneData(
                db.customers,
                {"id_user": ObjectId(ticket_data["id_reporter"])},
                {
                    "name": 1,
                    "service_number": 1,
                    "location": 1,
                    "phone_number": 1,
                },
            )
            if customer:
                ticket_data["customer"] = customer
                if not is_only_assignee:
                    PHONE_NUMBERS.append(customer.get("phone_number"))

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
            v_message += f"*Alamat*: {ticket_data.get('customer', '').get('location', '').get('address', '-')}\n"
        v_message += f"*Deskripsi*: {ticket_data.get('description', '')}\n"

        for number in PHONE_NUMBERS:
            params = {
                "api_key": WHATSAPP_API_KEY,
                "sender": WHATSAPP_BOT_NUMBER,
                "number": f"62{number}",
                "message": v_message,
            }
            whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
            requests.post(whatsapp_api_url, json=params, timeout=60)
    except Exception as e:
        print(e)
        await CreateWhatsappErrorNotification(db, str(e))


async def SendWhatsappTicketClosedMessage(db, id_ticket: str):
    try:
        PHONE_NUMBERS = [WHATSAPP_ADMIN_NUMBER]
        ticket_data = await GetOneData(db.tickets, {"_id": ObjectId(id_ticket)})
        if not ticket_data:
            return

        assignee = await GetOneData(
            db.users,
            {"_id": ObjectId(ticket_data["id_assignee"])},
            {"name": 1, "phone_number": 1},
        )
        if assignee:
            PHONE_NUMBERS.append(assignee.get("phone_number"))
            ticket_data["assignee"] = assignee

        if ticket_data["type"] != TicketTypeData.FOM.value:
            customer = await GetOneData(
                db.customers,
                {"id_user": ObjectId(ticket_data["id_reporter"])},
                {
                    "name": 1,
                    "service_number": 1,
                    "location": 1,
                    "phone_number": 1,
                },
            )
            if customer:
                PHONE_NUMBERS.append(customer.get("phone_number"))
                ticket_data["customer"] = customer

        v_message = f"*Tiket CLOSED - {ticket_data.get('title', '')}*\n\n"
        v_message += f"*Kode Tiket*: #{ticket_data.get('name', '-')}\n"
        if "assignee" in ticket_data:
            v_message += f"*Teknisi*: {ticket_data.get('assignee', '').get('name')}\n\n"
        if "customer" in ticket_data:
            v_message += (
                f"*Nama Pelanggan*: {ticket_data.get('customer', '').get('name')}\n"
            )
            v_message += f"*Nomor Layanan*: {ticket_data.get('customer', '').get('service_number')}\n"
            v_message += f"*Alamat*: {ticket_data.get('customer', '').get('location', '').get('address', '-')}\n"
        v_message += f"*Deskripsi*: {ticket_data.get('description', '')}\n"
        if ticket_data.get("confirm_message"):
            v_message += f"*Pesan Konfirmasi*: {ticket_data.get('confirm_message', '')}"

        for number in PHONE_NUMBERS:
            params = {
                "api_key": WHATSAPP_API_KEY,
                "sender": WHATSAPP_BOT_NUMBER,
                "number": f"62{number}",
                "message": v_message,
            }
            whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
            requests.post(whatsapp_api_url, json=params, timeout=60)
    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))


async def SendWhatsappFeeRequestedMessage(db, name: str, nominal: int, reason: str):
    try:
        v_message = "*Permintaan Bonus Referral*\n\n"
        v_message += f"*Nama*: {name}\n"
        v_message += f"*Nominal*: Rp{ThousandSeparator(nominal)}\n"
        v_message += f"*Alasan*: {reason}\n"

        params = {
            "api_key": WHATSAPP_API_KEY,
            "sender": WHATSAPP_BOT_NUMBER,
            "number": f"62{WHATSAPP_ADMIN_NUMBER}",
            "message": v_message,
        }
        whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)
    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))

async def SendWhatsappPaymentSuccessBillMessage(db, id_invoice):
    try:
        invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
        whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
        whatsapp_message = await GetOneData(
            db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
        )
        customer_data = await GetOneData(
            db.customers, {"_id": ObjectId(invoice_data.get("id_customer"))}
        )

        if (
            not invoice_data
            or not whatsapp_bot
            or not whatsapp_message
            or not customer_data
        ):
            return

        message = whatsapp_message.get("paid", "")

        # ✅ Tangani bulan secara dinamis
        try:
            bulan_str = MONTH_DICTIONARY[int(invoice_data.get("month"))]
        except Exception:
            bulan_str = "-"

        # 🔁 Siapkan field pengganti
        fields_to_replace = {
            "[nama_pelanggan]": customer_data.get("name", "-"),
            "[no_servis]": customer_data.get("service_number", "-"),
            "[nama_paket]": ", ".join([
                pkg.get("name", "-") for pkg in invoice_data.get("package", [])
            ]),
            "[jumlah_tagihan]": ThousandSeparator(invoice_data.get("amount", 0)),
            "[status]": "SUDAH DIBAYAR",
            "[hari]": GetCurrentDateTime().strftime("%d"),
            "[bulan]": bulan_str,
            "[tahun]": GetCurrentDateTime().strftime("%Y"),
            "[metode_bayar]": invoice_data.get("payment", {}).get("method", "-"),
            "[thanks_wa]": whatsapp_message.get("advance", {}).get("thanks_message", ""),
        }

        # 🔁 Ganti semua placeholder
        for key, value in fields_to_replace.items():
            try:
                message = message.replace(key, str(value))
            except Exception:
                message = message.replace(key, "-")

        # 🔗 Kirim ke WhatsApp Gateway
        params = {
            "api_key": WHATSAPP_API_KEY,
            "sender": WHATSAPP_BOT_NUMBER,
            "number": f"62{str(customer_data.get('phone_number', '')).lstrip('0')}",
            "message": message,
        }

        whatsapp_api_url = f"{WHATSAPP_GATEWAY_URL}/send-message"
        requests.post(whatsapp_api_url, json=params, timeout=60)

    except Exception as e:
        await CreateWhatsappErrorNotification(db, str(e))
