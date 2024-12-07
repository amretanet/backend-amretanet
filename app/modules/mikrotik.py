from bson import ObjectId
from app.modules.generals import AddURLHTTPProtocol
from app.modules.crud_operations import GetOneData
from urllib.parse import urljoin
import requests
from requests.auth import HTTPBasicAuth


async def CreateMikrotikPPPSecret(
    db,
    id_router: str,
    customer_name: str,
    profile: str,
    service_number: int,
):
    try:
        exist_router = await GetOneData(db.router, {"_id": ObjectId(id_router)})
        if not exist_router:
            return None

        host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
        url = urljoin(host, "/rest/ppp/secret/add")
        username = exist_router.get("username", "")
        password = exist_router.get("password", "")
        data = {
            "name": service_number,
            "password": service_number,
            "service": "ppp",
            "profile": profile,
            "comment": customer_name,
        }

        response = requests.post(url, json=data, auth=HTTPBasicAuth(username, password))
        result = response.json()
        if response.status_code == 200:
            return result.get("ret", None)

        return None
    except Exception:
        return None


async def UpdateMikrotikPPPSecret(
    db,
    id_secret: str,
    id_router: str,
    customer_name: str,
    profile: str,
    service_number: int,
    disabled: bool,
):
    try:
        exist_router = await GetOneData(db.router, {"_id": ObjectId(id_router)})
        if not exist_router:
            return False

        host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
        url = urljoin(host, "/rest/ppp/secret")
        username = exist_router.get("username", "")
        password = exist_router.get("password", "")
        data = {
            "name": service_number,
            "password": service_number,
            "service": "ppp",
            "profile": profile,
            "comment": customer_name,
            "disabled": disabled,
        }

        response = requests.put(
            f"{url}/{id_secret}", json=data, auth=HTTPBasicAuth(username, password)
        )
        if response.status_code == 201:
            return True

        return False
    except Exception:
        return False


async def DeleteMikrotikPPPSecret(db, id_router: str, id_secret: str):
    try:
        exist_router = await GetOneData(db.router, {"_id": ObjectId(id_router)})
        if not exist_router:
            return False

        host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
        url = urljoin(host, "/rest/ppp/secret")
        username = exist_router.get("username", "")
        password = exist_router.get("password", "")

        response = requests.delete(
            f"{url}/{id_secret}", auth=HTTPBasicAuth(username, password)
        )
        if response.status_code == 200:
            return True
        return False
    except Exception:
        return False
