import os
import requests
from dotenv import load_dotenv

load_dotenv()

MOOTA_API_TOKEN = os.getenv("MOOTA_API_TOKEN")
MOOTA_DEFAULT_BANK_ACCOUNT_ID = os.getenv("MOOTA_DEFAULT_BANK_ACCOUNT_ID")


async def GetMootaMutationTracking():
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {MOOTA_API_TOKEN}",
    }

    url = "https://app.moota.co/api/v2/mutation-tracking?page=&per_page="

    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except requests.exceptions.RequestException as e:
        return str(e)


async def GetDetailMootaMutation(trx_id: str):
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {MOOTA_API_TOKEN}",
    }

    url = f"https://app.moota.co/api/v2/mutation-tracking/detail?trx_id={trx_id}"

    try:
        response = requests.get(url, headers=headers)
        return response.json()
    except requests.exceptions.RequestException as e:
        return str(e)


async def CreateMootaMutation(customer_name: str, item_name: str, ammount: int):
    data = {
        "bank_account_id": MOOTA_DEFAULT_BANK_ACCOUNT_ID,
        "customers": {
            "name": customer_name,
        },
        "items": [
            {
                "name": item_name,
                "qty": 1,
                "price": ammount,
            }
        ],
        "total": ammount,
    }

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {MOOTA_API_TOKEN}",
    }

    url = "https://app.moota.co/api/v2/mutation-tracking"

    try:
        response = requests.post(url, json=data, headers=headers)
        return response.json()
    except requests.exceptions.RequestException:
        return None
