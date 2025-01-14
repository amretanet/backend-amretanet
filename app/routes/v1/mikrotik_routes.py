from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
)
from fastapi.responses import JSONResponse
from app.models.mikrotik import (
    MikrotikDeleteData,
    MikrotikSecretDeleteData,
    MikrotikUpdateData,
)
from app.modules.generals import AddURLHTTPProtocol
from app.models.users import UserData, UserRole
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import GetOneData
from app.modules.mikrotik import (
    DeleteMikrotikPPPProfileByID,
    DeleteMikrotikPPPSecretByID,
    UpdateMikrotikPPPSecretByID,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
import requests
from urllib.parse import urljoin
from requests.auth import HTTPBasicAuth
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)

router = APIRouter(prefix="/mikrotik", tags=["Mikrotik"])


@router.get("/interface")
async def get_interface_data(
    router: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    interface_data = []

    exist_router = await GetOneData(db.router, {"name": router})
    if not exist_router:
        return JSONResponse(content={"interface_data": interface_data})

    host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
    url = urljoin(host, "/rest/interface?type=ether,vlan")
    username = exist_router.get("username", "")
    password = exist_router.get("password", "")
    try:
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        if response.status_code == 200:
            interface_data = response.json()
    except requests.exceptions.RequestException as e:
        print(e)

    return JSONResponse(content={"interface_data": interface_data})


@router.get("/profile")
async def get_profile_data(
    router: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    profile_data = []

    exist_router = await GetOneData(db.router, {"name": router})
    if not exist_router:
        return JSONResponse(content={"profile_data": profile_data})

    host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
    url = urljoin(host, "/rest/ppp/profile")
    username = exist_router.get("username", "")
    password = exist_router.get("password", "")
    try:
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        if response.status_code == 200:
            profile_data = response.json()
    except requests.exceptions.RequestException as e:
        print(e)

    return JSONResponse(content={"profile_data": profile_data})


@router.put("/profile/delete/{id}")
async def delete_profile(
    id: str,
    data: MikrotikDeleteData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    is_success = await DeleteMikrotikPPPProfileByID(db, payload["router"], id)
    if not is_success:
        raise HTTPException(status_code=400, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})


@router.get("/secret")
async def get_secret_data(
    router: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    secret_data = []

    exist_router = await GetOneData(db.router, {"name": router})
    if not exist_router:
        return JSONResponse(content={"secret_data": secret_data})

    host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
    url = urljoin(host, "/rest/ppp/secret")
    username = exist_router.get("username", "")
    password = exist_router.get("password", "")
    try:
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        if response.status_code == 200:
            secret_data = response.json()
    except requests.exceptions.RequestException as e:
        print(e)

    return JSONResponse(content={"secret_data": secret_data})


@router.put("/secret/update/{id}")
async def update_secret(
    id: str,
    data: MikrotikUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    is_success = await UpdateMikrotikPPPSecretByID(db, payload["router"], id, payload)
    if not is_success:
        raise HTTPException(status_code=400, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/secret/delete/{id}")
async def delete_secret(
    id: str,
    data: MikrotikSecretDeleteData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    is_success = await DeleteMikrotikPPPSecretByID(
        db, payload["router"], id, payload["name"]
    )
    if not is_success:
        raise HTTPException(status_code=400, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})


@router.get("/system-resource")
async def get_system_resource_data(
    router: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    system_resource_data = []

    exist_router = await GetOneData(db.router, {"name": router})
    if not exist_router:
        return JSONResponse(content={"system_resource_data": system_resource_data})

    host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
    url = urljoin(host, "/rest/system/resource")
    username = exist_router.get("username", "")
    password = exist_router.get("password", "")
    try:
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        if response.status_code == 200:
            system_resource_data = response.json()
    except requests.exceptions.RequestException as e:
        print(e)

    return JSONResponse(content={"system_resource_data": system_resource_data})


@router.get("/user-stats")
async def get_user_stats_data(
    router: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    ppp = []
    secret = []

    exist_router = await GetOneData(db.router, {"name": router})
    if not exist_router:
        return JSONResponse(content={"ppp": ppp})

    host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
    ppp_url = urljoin(host, "/rest/ppp/active")
    secret_url = urljoin(host, "/rest/ppp/secret")
    username = exist_router.get("username", "")
    password = exist_router.get("password", "")
    try:
        ppp_response = requests.get(
            ppp_url, auth=HTTPBasicAuth(username, password), timeout=10
        )
        if ppp_response.status_code == 200:
            ppp = ppp_response.json()
        secret_response = requests.get(
            secret_url, auth=HTTPBasicAuth(username, password), timeout=10
        )
        if secret_response.status_code == 200:
            secret = secret_response.json()
    except requests.exceptions.RequestException as e:
        print(e)

    return JSONResponse(
        content={
            "ppp": len(ppp),
            "secret": len(secret),
        }
    )


@router.get("/log")
async def get_log_data(
    router: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    log_data = []

    exist_router = await GetOneData(db.router, {"name": router})
    if not exist_router:
        return JSONResponse(content={"log_data": log_data})

    host = AddURLHTTPProtocol(exist_router.get("ip_address", ""))
    url = urljoin(host, "/rest/log")
    username = exist_router.get("username", "")
    password = exist_router.get("password", "")
    try:
        response = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
        if response.status_code == 200:
            log_data = response.json()
    except requests.exceptions.RequestException as e:
        print(e)

    return JSONResponse(content={"log_data": log_data})
