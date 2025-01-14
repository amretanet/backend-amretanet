from bson import ObjectId
from fastapi.responses import JSONResponse
from app.modules.generals import AddURLHTTPProtocol
from app.modules.crud_operations import GetOneData
from urllib.parse import urljoin
import requests
from requests.auth import HTTPBasicAuth


def DeleteMikrotikInterface(host, username, password, pppoe_username):
    active_ppp_url = urljoin(host, f"/rest/ppp/active?name={pppoe_username}")
    response = requests.get(
        active_ppp_url, auth=HTTPBasicAuth(username, password), timeout=10
    )
    result = response.json()
    if len(result) > 0:
        ppp_id = result[0].get(".id", None)
        delete_url = urljoin(host, f"/rest/ppp/active/{ppp_id}")
        requests.delete(delete_url, auth=HTTPBasicAuth(username, password), timeout=10)


async def ActivateMikrotikPPPSecret(db, customer_data, disabled: bool = False):
    is_success = True
    try:
        pppoe_username = customer_data.get("pppoe_username", None)
        pppoe_password = customer_data.get("pppoe_password", None)
        id_router = customer_data.get("id_router", None)

        # check router
        exist_router = await GetOneData(db.router, {"_id": ObjectId(id_router)})
        if not exist_router:
            is_success = False

        # setup mikrotik credentials
        host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
        url = urljoin(host, f"/rest/ppp/secret?name={pppoe_username}")
        username = exist_router.get("username", "")
        password = exist_router.get("password", "")

        # get specified secret
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        result = response.json()
        secret_id = None
        if len(result) > 0:
            secret_id = result[0].get(".id", None)

        if secret_id:
            # update exist secret
            data = {
                "disabled": disabled,
            }
            if pppoe_username:
                data["name"] = pppoe_username
            if pppoe_password:
                data["password"] = pppoe_password

            url = urljoin(host, "/rest/ppp/secret")
            response = requests.patch(
                f"{url}/{secret_id}",
                json=data,
                auth=HTTPBasicAuth(username, password),
                timeout=10,
            )
            if response.status_code != 200:
                is_success = False
        else:
            # create new secret data
            package_data = await GetOneData(
                db.packages, {"_id": ObjectId(customer_data.get("id_package", None))}
            )
            if not package_data:
                is_success = False

            secret_data = {
                "name": pppoe_username,
                "password": pppoe_password,
                "service": "ppp",
                "profile": package_data.get("router_profile", "default"),
                "disabled": disabled,
                "comment": customer_data.get("name", "Undefined"),
            }
            url = urljoin(host, "/rest/ppp/secret/add")
            response = requests.post(
                url,
                json=secret_data,
                auth=HTTPBasicAuth(username, password),
                timeout=10,
            )
            result = response.json()
            if response.status_code != 200:
                is_success = False

        if disabled:
            DeleteMikrotikInterface(host, username, password, pppoe_username)
    except Exception as e:
        print(str(e))
        is_success = False

    return JSONResponse(content=is_success)


async def DeleteMikrotikPPPSecret(db, customer_data):
    try:
        id_router = customer_data.get("id_router", None)
        pppoe_username = customer_data.get("pppoe_username", None)

        # check router
        exist_router = await GetOneData(db.router, {"_id": ObjectId(id_router)})
        if not exist_router:
            return False

        # setup mikrotik credentials
        host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
        url = urljoin(host, f"/rest/ppp/secret?name={pppoe_username}")
        username = exist_router.get("username", "")
        password = exist_router.get("password", "")

        # get specified secret
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        result = response.json()
        if len(result) > 0:
            secret_id = result[0].get(".id", None)
            url = urljoin(host, "/rest/ppp/secret")
            response = requests.delete(
                f"{url}/{secret_id}", auth=HTTPBasicAuth(username, password), timeout=10
            )
            if response.status_code != 200:
                return False

            DeleteMikrotikInterface(host, username, password, pppoe_username)
        return True
    except Exception:
        return False


async def UpdateMikrotikPPPSecretByID(db, router, id_secret, payload):
    is_success = True
    try:
        # check router
        exist_router = await GetOneData(db.router, {"name": router})
        if not exist_router:
            is_success = False

        # setup mikrotik credentials
        username = exist_router.get("username", "")
        password = exist_router.get("password", "")

        # update exist secret
        data = {}
        if "disabled" in payload:
            data["disabled"] = payload["disabled"]
        if "name" in payload:
            data["name"] = payload["name"]
        if "password" in payload:
            data["password"] = payload["password"]
        if "comment" in payload:
            data["comment"] = payload["comment"]

        host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
        url = urljoin(host, f"/rest/ppp/secret/{id_secret}")
        response = requests.patch(
            url, json=data, auth=HTTPBasicAuth(username, password), timeout=10
        )
        if response.status_code != 200:
            is_success = False

        if payload.get("disabled") and payload.get("name"):
            DeleteMikrotikInterface(host, username, password, payload["name"])
    except Exception as e:
        print(str(e))
        is_success = False

    return JSONResponse(content=is_success)


async def DeleteMikrotikPPPSecretByID(db, router, id_secret: str, secret_name: str):
    is_success: True
    try:
        # check router
        exist_router = await GetOneData(db.router, {"name": router})
        if not exist_router:
            return False

        # setup mikrotik credentials
        host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
        username = exist_router.get("username", "")
        password = exist_router.get("password", "")

        # get specified secret
        url = urljoin(host, f"/rest/ppp/secret/{id_secret}")
        response = requests.delete(
            url, auth=HTTPBasicAuth(username, password), timeout=10
        )
        if response.status_code != 200:
            is_success = False

        DeleteMikrotikInterface(host, username, password, secret_name)
    except Exception:
        is_success = False

    return JSONResponse(content=is_success)


async def DeleteMikrotikPPPProfileByID(db, router, id_profile: str):
    is_success: True
    try:
        # check router
        exist_router = await GetOneData(db.router, {"name": router})
        if not exist_router:
            return False

        # setup mikrotik credentials
        host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
        username = exist_router.get("username", "")
        password = exist_router.get("password", "")

        # get specified profile
        url = urljoin(host, f"/rest/ppp/profile/{id_profile}")
        response = requests.delete(
            url, auth=HTTPBasicAuth(username, password), timeout=10
        )
        if response.status_code != 200:
            is_success = False
    except Exception:
        is_success = False

    return JSONResponse(content=is_success)
