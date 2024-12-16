import os
from urllib.parse import urlencode
from bson import ObjectId
import requests
from app.modules.generals import ThousandSeparator, DateIDFormatter
from app.modules.crud_operations import GetOneData
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_INSTALATION_THREAD_ID = os.getenv("TELEGRAM_INSTALATION_THREAD_ID")
TELEGRAM_MAINTENANCE_THREAD_ID = os.getenv("TELEGRAM_MAINTENANCE_THREAD_ID")
TELEGRAM_PAYMENT_THREAD_ID = os.getenv("TELEGRAM_PAYMENT_THREAD_ID")


async def SendTelegramInstalationMessage():
    v_message = "*Work Order - Pemasangan Baru*\n\n"
    v_message += f"Kode Tiket: TKT-0121\n"
    v_message += f"Teknisi: Nama Teknisi\n\n"
    v_message += f"Nama Pelanggan: Nama Pelanggan\n"
    v_message += f"Nomor Layanan: 288733\n"
    v_message += f"Alamat: Cimahi Bandung Barat\n\n"
    v_message += f"Waktu Pemasangan: 20 Desember 2023\n"

    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": TELEGRAM_INSTALATION_THREAD_ID,
        "text": v_message,
        "parse_mode": "Markdown",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "📞Telp Pelanggan",
                        "url": "https://example.com",
                    },
                    {
                        "text": "📍Cek Lokasi",
                        "url": "https://example.com",
                    },
                ]
            ]
        },
    }
    telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(telegram_api_url, json=data)
    print(response)


async def SendTelegramPaymentMessage(db, id_invoice):
    invoice_data = await GetOneData(db.invoices, {"_id": ObjectId(id_invoice)})
    if not invoice_data:
        return

    v_message = "*✅ PEMBAYARAN BERHASIL*\n\n"
    v_message += f'Nama: {invoice_data.get("name","Pelanggan")}\n'
    v_message += f'Nomor Layanan: {invoice_data.get("service_number","-")}\n'
    v_message += f'Tagihan: Rp{ThousandSeparator(invoice_data.get("amount",0))}\n'
    v_message += f'Periode: {DateIDFormatter(invoice_data.get("due_date"))}\n'
    v_message += f'Tanggal Pembayaran: {invoice_data.get("payment").get("paid_at")}\n'
    v_message += f'Metode Pembayaran: {invoice_data.get("payment").get("method")}\n'
    if invoice_data.get("payment").get("method") in ["TRANSFER", "QRIS"]:
        v_message += (
            f"Bukti Pembayaran: {invoice_data.get("payment").get("image_url")}\n"
        )

    params = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_thread_id": TELEGRAM_PAYMENT_THREAD_ID,
        "text": v_message,
        "parse_mode": "Markdown",
    }
    telegram_api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage?{urlencode(params)}"
    requests.get(telegram_api_url)
