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
from app.models.users import UserData, UserRole
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.mikrotik import GetMikrotikRouterDataByName, MikrotikConnection
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
import requests
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from librouteros.query import Key, Or

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

    host, username, password, port = await GetMikrotikRouterDataByName(db, router)
    if not host:
        return JSONResponse(content={"message": SYSTEM_ERROR_MESSAGE})

    try:
        mikrotik = MikrotikConnection(host, username, password, port)
        type = Key("type")
        for row in (
            mikrotik.path("/interface")
            .select()
            .where(
                Or(
                    type == "ether",
                    type == "vlan",
                ),
            )
        ):
            interface_data.append(row)
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

    host, username, password, port = await GetMikrotikRouterDataByName(db, router)
    if not host:
        return JSONResponse(content={"profile_data": profile_data})
    try:
        mikrotik = MikrotikConnection(host, username, password, port)
        for row in mikrotik.path("/ppp/profile").select():
            profile_data.append(row)
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
    host, username, password, port = await GetMikrotikRouterDataByName(
        db, payload["router"]
    )
    if not host:
        return JSONResponse(content={"message": SYSTEM_ERROR_MESSAGE})
    mikrotik = MikrotikConnection(host, username, password, port)
    mikrotik.path("/ppp/profile").remove(id)
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

    host, username, password, port = await GetMikrotikRouterDataByName(db, router)
    if not host:
        return JSONResponse(content={"secret_data": secret_data})

    try:
        mikrotik = MikrotikConnection(host, username, password, port)
        for row in mikrotik.path("/ppp/secret").select():
            row["name"] = str(row.get("name", ""))
            row["password"] = str(row.get("password", ""))
            secret_data.append(row)
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
    host, username, password, port = await GetMikrotikRouterDataByName(
        db, payload["router"]
    )
    if not host:
        return JSONResponse(content={"message": SYSTEM_ERROR_MESSAGE})

    update_data = {
        ".id": id,
    }
    if "name" in payload:
        update_data["name"] = payload["name"]
    if "password" in payload:
        update_data["password"] = payload["password"]
    if "comment" in payload:
        update_data["comment"] = payload["comment"]
    if "disabled" in payload:
        update_data["disabled"] = payload["disabled"]

    mikrotik = MikrotikConnection(host, username, password, port)
    mikrotik.path("/ppp/secret").update(**update_data)
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
    host, username, password, port = await GetMikrotikRouterDataByName(
        db, payload["router"]
    )
    if not host:
        return JSONResponse(content={"message": SYSTEM_ERROR_MESSAGE})

    mikrotik = MikrotikConnection(host, username, password, port)
    mikrotik.path("/ppp/secret").remove(id)
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

    host, username, password, port = await GetMikrotikRouterDataByName(db, router)
    if not host:
        return JSONResponse(content={"message": SYSTEM_ERROR_MESSAGE})

    try:
        mikrotik = MikrotikConnection(host, username, password, port)
        for row in mikrotik.path("/system/resource").select():
            system_resource_data.append(row)
    except requests.exceptions.RequestException as e:
        print(e)

    return JSONResponse(
        content={
            "system_resource_data": system_resource_data[0]
            if len(system_resource_data) > 0
            else {}
        }
    )


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

    host, username, password, port = await GetMikrotikRouterDataByName(db, router)
    if not host:
        return JSONResponse(content={"message": SYSTEM_ERROR_MESSAGE})

    try:
        mikrotik = MikrotikConnection(host, username, password, port)
        for row in mikrotik.path("/ppp/active").select():
            ppp.append(row)
        for row in mikrotik.path("/ppp/secret").select():
            secret.append(row)
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

    host, username, password, port = await GetMikrotikRouterDataByName(db, router)
    if not host:
        return JSONResponse(content={"message": SYSTEM_ERROR_MESSAGE})

    try:
        mikrotik = MikrotikConnection(host, username, password, port)
        for row in mikrotik.path("/log").select():
            log_data.append(row)
    except requests.exceptions.RequestException as e:
        print(e)

    return JSONResponse(content={"log_data": log_data})


@router.get("/reboot")
async def reboot_mikrotik(
    router: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )

    host, username, password, port = await GetMikrotikRouterDataByName(db, router)
    if not host:
        return JSONResponse(content={"message": SYSTEM_ERROR_MESSAGE})

    try:
        mikrotik = MikrotikConnection(host, username, password, port)
        mikrotik("/system/reboot")
    except requests.exceptions.RequestException as e:
        print(e)

    return JSONResponse(content={"message": "Mikrotik Telah Direboot"})
