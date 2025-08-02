import requests
import os
from dotenv import load_dotenv

load_dotenv()

BABLAST_API_URL = os.getenv("BABLAST_API_URL")
BABLAST_API_TOKEN = os.getenv("BABLAST_API_TOKEN")


async def SendBablastWhatsappSingleMessage(destination_number: str, message: str):
    url = f"{BABLAST_API_URL}/send"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BABLAST_API_TOKEN}",
    }
    body = {
        "phone": destination_number,
        "message": message,
    }

    try:
        res = requests.post(url=url, headers=headers, json=body, timeout=15)
        res.raise_for_status()
        return {"success": True, "data": res.json()}
    except requests.HTTPError as http_err:
        return {
            "success": False,
            "error": f"HTTP error: {http_err}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


async def SendBablastWhatsappBulkMessage(
    group_name: str = "Pesan Broadcast",
    delay: int = 30,
    message: str = "",
    destination_contacts: list = [],
):
    url = f"{BABLAST_API_URL}/send/bulk"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {BABLAST_API_TOKEN}",
    }
    contacts = [
        {
            "nama": item.get("name", "Tidak Diketahui"),
            "phone": f"62{item.get('phone_number')}",
        }
        for item in destination_contacts
    ]
    body = {
        "group_name": group_name,
        "message": message,
        "delay": delay * 1000,
        "contacts": contacts,
    }

    try:
        res = requests.post(url=url, headers=headers, json=body, timeout=15)
        res.raise_for_status()
        return {"success": True, "data": res.json()}
    except requests.HTTPError as http_err:
        return {
            "success": False,
            "error": f"HTTP error: {http_err}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
