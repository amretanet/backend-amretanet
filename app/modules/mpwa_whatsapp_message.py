import os
import requests
from dotenv import load_dotenv

load_dotenv()

MPWA_API_URL = os.getenv("MPWA_API_URL")
MPWA_API_TOKEN = os.getenv("MPWA_API_TOKEN")
WHATSAPP_ADMIN_NUMBER = os.getenv("WHATSAPP_ADMIN_NUMBER")
WHATSAPP_BOT_NUMBER = os.getenv("WHATSAPP_BOT_NUMBER")


async def SendMPWAWhatsappSingleMessage(destination_number: str, message: str):
    url = f"{MPWA_API_URL}/send-message"
    body = {
        "api_key": MPWA_API_TOKEN,
        "sender": WHATSAPP_BOT_NUMBER,
        "number": destination_number,
        "message": message,
    }
    try:
        res = requests.post(url=url, json=body, timeout=15)
        res.raise_for_status()
        return {"success": True, "data": res.json()}
    except requests.HTTPError as http_err:
        return {
            "success": False,
            "error": f"HTTP error: {http_err}",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
