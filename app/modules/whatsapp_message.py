from bson import ObjectId
from app.models.whatsapp_messages import WhatsappGatewayType
from app.models.tickets import TicketTypeData
from app.modules.crud_operations import (
    CreateOneData,
    GetAggregateData,
    GetOneData,
    UpdateOneData,
)
import asyncio
from app.modules.mpwa_whatsapp_message import SendMPWAWhatsappSingleMessage
from app.modules.bablast_whatsapp_message import (
    SendBablastWhatsappBulkMessage,
    SendBablastWhatsappSingleMessage,
)
from app.modules.generals import DateIDFormatter, GetCurrentDateTime, ThousandSeparator
import os
from app.models.notifications import NotificationTypeData
from app.models.users import UserRole
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_ADMIN_NUMBER = os.getenv("WHATSAPP_ADMIN_NUMBER")
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
WHATSAPP_DELAY_TIME_SECONDS = int(os.getenv("WHATSAPP_DELAY_TIME_SECONDS"))


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


async def GetCurrentWhatsappGateway(db):
    whatsapp_gateway = WhatsappGatewayType.BABLAST.value
    whatsapp_config = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if whatsapp_config:
        whatsapp_gateway = whatsapp_config.get("advance", {}).get(
            "whatsapp_gateway", WhatsappGatewayType.BABLAST.value
        )

    return whatsapp_gateway


def WhatsappMessageFormatter(title: str, body: str):
    formatted_message = f"*{title}*\n{body}"
    return formatted_message


async def SendWhatsappSingleMessage(db, destination_number: str, message: str):
    response = None
    whatsapp_gateway = await GetCurrentWhatsappGateway(db)
    destination_number = f"62{destination_number}"
    if whatsapp_gateway == WhatsappGatewayType.MPWA.value:
        response = await SendMPWAWhatsappSingleMessage(destination_number, message)
    else:
        response = await SendBablastWhatsappSingleMessage(destination_number, message)

    if not response.get("success"):
        await CreateWhatsappErrorNotification(db, response.get("data"))

    return response


async def SendWhatsappBroadcastMessage(
    db, destination_contacts: list[str], message: str
):
    response = None
    whatsapp_gateway = await GetCurrentWhatsappGateway(db)

    if whatsapp_gateway == WhatsappGatewayType.MPWA.value:
        for destination in destination_contacts:
            try:
                destination_number = f"62{destination.get('phone_number')}"
                response = await SendMPWAWhatsappSingleMessage(
                    destination_number, message
                )
                await asyncio.sleep(WHATSAPP_DELAY_TIME_SECONDS)
            except Exception as e:
                print(str(e))
                continue
    else:
        response = await SendBablastWhatsappBulkMessage(
            delay=WHATSAPP_DELAY_TIME_SECONDS,
            destination_contacts=destination_contacts,
            message=message,
        )

    if not response.get("success"):
        await CreateWhatsappErrorNotification(db, response.get("data"))

    return response


async def SendWhatsappCustomerActivatedMessage(db, id_customer):
    customer_data = await GetOneData(db.customers, {"_id": ObjectId(id_customer)})
    whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
    whatsapp_config = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if not customer_data or not whatsapp_bot or not whatsapp_config:
        return

    message = whatsapp_config.get("activate", "")
    fields_to_replace = {
        "[nama_pelanggan]": customer_data.get("name", "-"),
        "[no_servis]": customer_data.get("service_number", "-"),
    }

    for key, value in fields_to_replace.items():
        try:
            message = message.replace(key, str(value))
        except Exception:
            message = message.replace(key, "-")

    response = await SendWhatsappSingleMessage(
        db, customer_data["phone_number"], message
    )
    return response


async def SendWhatsappPaymentCreatedMessage(db, invoice_ids: list):
    whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
    whatsapp_config = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if not whatsapp_bot or not whatsapp_config:
        return

    for id_invoice in invoice_ids:
        try:
            invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
            if not invoice_data:
                continue

            customer_data = await GetOneData(
                db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
            )
            if not customer_data:
                continue

            message = whatsapp_config.get("billing", "")
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
                "[footer_wa]": whatsapp_config.get("advance", {}).get("footer", ""),
            }

            for key, value in fields_to_replace.items():
                try:
                    message = message.replace(key, str(value))
                except Exception:
                    message = message.replace(key, "-")

            response = await SendWhatsappSingleMessage(
                db, customer_data["phone_number"], message
            )
            if response and response.get("success"):
                await UpdateOneData(
                    db.invoices,
                    {"_id": ObjectId(id_invoice)},
                    {"$set": {"is_whatsapp_sended": True}},
                )

            await asyncio.sleep(WHATSAPP_DELAY_TIME_SECONDS)
        except Exception as e:
            print(str(e))
            continue

    return {"message": "Whatsapp Telah Dikirimkan!"}


async def SendWhatsappPaymentReminderMessage(db, invoice_ids: list):
    whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
    whatsapp_config = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if not whatsapp_bot or not whatsapp_config:
        return

    for id_invoice in invoice_ids:
        try:
            invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
            if not invoice_data:
                continue

            customer_data = await GetOneData(
                db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
            )
            if not customer_data:
                continue

            message = whatsapp_config.get("reminder", "")
            fields_to_replace = {
                "[nama_pelanggan]": customer_data.get("name", "-"),
                "[jumlah_tagihan]": ThousandSeparator(invoice_data.get("amount", 0)),
                "[link]": f"{FRONTEND_DOMAIN}/quick-payment?id={id_invoice}",
                "[footer_wa]": whatsapp_config.get("advance", {}).get("footer", ""),
            }

            for key, value in fields_to_replace.items():
                try:
                    message = message.replace(key, str(value))
                except Exception:
                    message = message.replace(key, "-")

            response = await SendWhatsappSingleMessage(
                db, customer_data["phone_number"], message
            )
            if response.get("success"):
                await UpdateOneData(
                    db.invoices,
                    {"_id": ObjectId(id_invoice)},
                    {"$set": {"is_whatsapp_reminder_sended": True}},
                )

            await asyncio.sleep(WHATSAPP_DELAY_TIME_SECONDS)
        except Exception as e:
            print(str(e))
            continue

    return {"message": "Pengingat Telah Dikirimkan!"}


async def SendWhatsappPaymentOverdueMessage(db, invoice_ids):
    whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
    whatsapp_config = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if not whatsapp_bot or not whatsapp_config:
        return

    for id_invoice in invoice_ids:
        try:
            invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
            if not invoice_data:
                continue
            customer_data = await GetOneData(
                db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
            )
            if not customer_data:
                continue

            message = whatsapp_config.get("overdue", "")
            fields_to_replace = {
                "[judul]": f"*{whatsapp_config.get('advance', {}).get('header', '')}*",
                "[nama_pelanggan]": customer_data.get("name", "-"),
                "[no_servis]": customer_data.get("service_number", "-"),
                "[link]": f"{FRONTEND_DOMAIN}/quick-payment?id={id_invoice}",
            }

            for key, value in fields_to_replace.items():
                try:
                    message = message.replace(key, str(value))
                except Exception:
                    message = message.replace(key, "-")

            response = await SendWhatsappSingleMessage(
                db, customer_data["phone_number"], message
            )
            if response.get("success"):
                await UpdateOneData(
                    db.invoices,
                    {"_id": ObjectId(id_invoice)},
                    {"$set": {"is_whatsapp_overdue_sended": True}},
                )

            await asyncio.sleep(WHATSAPP_DELAY_TIME_SECONDS)
        except Exception as e:
            print(str(e))
            continue

    return {"message": "Pesan Overdue Telah Dikirimkan!"}


async def SendWhatsappIsolirMessage(db, invoice_ids):
    whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
    whatsapp_config = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if not whatsapp_bot or not whatsapp_config:
        return

    for id_invoice in invoice_ids:
        try:
            invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
            if not invoice_data:
                continue

            customer_data = await GetOneData(
                db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
            )
            if not customer_data:
                continue

            message = whatsapp_config.get("isolir", "")
            fields_to_replace = {
                "[nama_pelanggan]": customer_data.get("name", "-"),
                "[jumlah_tagihan]": ThousandSeparator(invoice_data.get("amount", 0)),
            }

            for key, value in fields_to_replace.items():
                try:
                    message = message.replace(key, str(value))
                except Exception:
                    message = message.replace(key, "-")

            response = await SendWhatsappSingleMessage(
                db, customer_data["phone_number"], message
            )
            if response.get("success"):
                await UpdateOneData(
                    db.invoices,
                    {"_id": ObjectId(id_invoice)},
                    {"$set": {"is_whatsapp_isolir_sended": True}},
                )

            await asyncio.sleep(WHATSAPP_DELAY_TIME_SECONDS)
        except Exception as e:
            await CreateWhatsappErrorNotification(db, str(e))

    return {"message": "Pesan Isolir Telah Dikirimkan!"}


async def SendWhatsappPaymentSuccessMessage(db, invoice_ids: list):
    whatsapp_bot = await GetOneData(db.configurations, {"type": "WHATSAPP_BOT"})
    whatsapp_config = await GetOneData(
        db.configurations, {"type": "WHATSAPP_MESSAGE_TEMPLATE"}
    )
    if not whatsapp_bot or not whatsapp_config:
        return

    for id_invoice in invoice_ids:
        try:
            invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
            if not invoice_data:
                continue

            customer_data = await GetOneData(
                db.customers, {"_id": ObjectId(invoice_data["id_customer"])}
            )
            if not customer_data:
                continue

            message = whatsapp_config.get("paid", "")
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
                "[thanks_wa]": whatsapp_config.get("advance", "").get(
                    "thanks_message", ""
                ),
            }

            for key, value in fields_to_replace.items():
                try:
                    message = message.replace(key, str(value))
                except Exception:
                    message = message.replace(key, "-")

            response = await SendWhatsappSingleMessage(
                db, customer_data["phone_number"], message
            )
            await asyncio.sleep(WHATSAPP_DELAY_TIME_SECONDS)
        except Exception as e:
            print(str(e))
            continue

    return {"message": "Pesan Pembayaran Telah Dikirimkan!"}


async def SendWhatsappTicketOpenMessage(
    db, id_ticket: str, is_only_assignee: bool = False
):
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
        try:
            response = await SendWhatsappSingleMessage(db, number, v_message)
            await asyncio.sleep(WHATSAPP_DELAY_TIME_SECONDS)
        except Exception as e:
            print(str(e))
            continue

    return {"message": "Pesan Telah Dikirimkan!"}


async def SendWhatsappTicketClosedMessage(db, id_ticket: str):
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
        try:
            response = await SendWhatsappSingleMessage(db, number, v_message)
            await asyncio.sleep(WHATSAPP_DELAY_TIME_SECONDS)
        except Exception as e:
            print(str(e))
            continue


async def SendWhatsappFeeRequestedMessage(db, name: str, nominal: int, reason: str):
    v_message = "*Permintaan Bonus Referral*\n\n"
    v_message += f"*Nama*: {name}\n"
    v_message += f"*Nominal*: Rp{ThousandSeparator(nominal)}\n"
    v_message += f"*Alasan*: {reason}\n"

    response = await SendWhatsappSingleMessage(db, WHATSAPP_ADMIN_NUMBER, v_message)
    return response


async def SendWhatsappPaymentSuccessBillMessage(db, invoice_ids):
    for id_invoice in invoice_ids:
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
                "[nama_paket]": ", ".join(
                    [pkg.get("name", "-") for pkg in invoice_data.get("package", [])]
                ),
                "[jumlah_tagihan]": ThousandSeparator(invoice_data.get("amount", 0)),
                "[status]": "SUDAH DIBAYAR",
                "[hari]": GetCurrentDateTime().strftime("%d"),
                "[bulan]": bulan_str,
                "[tahun]": GetCurrentDateTime().strftime("%Y"),
                "[metode_bayar]": invoice_data.get("payment", {}).get("method", "-"),
                "[thanks_wa]": whatsapp_message.get("advance", {}).get(
                    "thanks_message", ""
                ),
            }

            # 🔁 Ganti semua placeholder
            for key, value in fields_to_replace.items():
                try:
                    message = message.replace(key, str(value))
                except Exception:
                    message = message.replace(key, "-")

            # 🔗 Kirim ke WhatsApp Gateway
            phone_number = str(customer_data.get("phone_number", "")).lstrip("0")
            response = await SendWhatsappSingleMessage(db, phone_number, message)
            await asyncio.sleep(WHATSAPP_DELAY_TIME_SECONDS)
        except Exception as e:
            print(str(e))
            continue

    return {"message": "Pesan Telah Dikirimkan!"}
