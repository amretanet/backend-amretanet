from urllib.parse import urlencode, urljoin
from bson import ObjectId
import requests
from app.modules.crud_operations import GetOneData
from app.modules.generals import GetCurrentDateTime, ThousandSeparator

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


def WhatsappMessageFormatter(title: str, body: str):
    formatted_message = f"*{title}*\n{body}"
    return formatted_message


async def SendPaymentCreatedMessage(db, id_invoice, service_url):
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
        "[link]": f"{service_url}invoice/pdf/{id_invoice}",
        "[footer_wa]": whatsapp_message.get("advance", "").get("footer", ""),
    }

    for key, value in fields_to_replace.items():
        try:
            message = message.replace(key, str(value))
        except Exception:
            message = message.replace(key, "-")

    API_URL = urljoin(whatsapp_bot["url_gateway"], "/send-message")
    API_TOKEN = whatsapp_bot["api_key"]
    params = {
        "api_key": API_TOKEN,
        "sender": f"62{whatsapp_bot['bot_number']}",
        "number": f"62{customer_data['phone_number']}",
        "message": message,
    }
    final_url = f"{API_URL}?{urlencode(params)}"
    requests.post(final_url, json=params, timeout=10)


async def SendPaymentSuccessMessage(db, id_invoice):
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
        "[thanks_wa]": whatsapp_message.get("advance", "").get("thanks_message", ""),
    }

    for key, value in fields_to_replace.items():
        try:
            message = message.replace(key, str(value))
        except Exception:
            message = message.replace(key, "-")

    API_URL = urljoin(whatsapp_bot["url_gateway"], "/send-message")
    API_TOKEN = whatsapp_bot["api_key"]
    params = {
        "api_key": API_TOKEN,
        "sender": f"62{whatsapp_bot['bot_number']}",
        "number": f"62{customer_data['phone_number']}",
        "message": message,
    }
    final_url = f"{API_URL}?{urlencode(params)}"
    requests.post(final_url, json=params, timeout=10)
