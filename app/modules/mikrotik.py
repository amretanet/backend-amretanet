from bson import ObjectId
from app.modules.generals import GetCurrentDateTime
from app.modules.crud_operations import CreateOneData, GetAggregateData, GetOneData
from app.models.notifications import NotificationTypeData
from app.models.users import UserRole
from librouteros import connect
from librouteros.query import Key


async def GetMikrotikRouterDataByName(db, router_name: str):
    host = None
    username = None
    password = None
    port = None
    router_data = await GetOneData(db.router, {"name": router_name})
    if router_data:
        host = router_data.get("ip_address", None)
        username = router_data.get("username", None)
        password = router_data.get("password", None)
        port = router_data.get("api_port", None)

    return host, username, password, port


async def GetMikrotikRouterDataByID(db, id_router: str):
    host = None
    username = None
    password = None
    port = None
    router_data = await GetOneData(db.router, {"_id": ObjectId(id_router)})
    if router_data:
        host = router_data.get("ip_address", None)
        username = router_data.get("username", None)
        password = router_data.get("password", None)
        port = router_data.get("api_port", None)

    return host, username, password, port


def MikrotikConnection(host: str, username: str, password: str, port: int):
    connection = connect(username=username, password=password, host=host, port=port)
    return connection


async def CreateMikrotikErrorNotification(db, description: str):
    notification_data = {
        "title": "Mikrotik Message Error",
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
        await CreateOneData(db.notifications, notification_data)


async def ActivateMikrotikPPPSecret(db, customer_data, disabled: bool = False):
    try:
        pppoe_username = customer_data.get("pppoe_username", None)
        pppoe_password = customer_data.get("pppoe_password", None)
        id_router = customer_data.get("id_router", None)

        # check router
        host, username, password, port = await GetMikrotikRouterDataByID(db, id_router)
        if not host:
            return False

        secret_data = []
        secret_id = None
        mikrotik = MikrotikConnection(host, username, password, port)
        name = Key("name")
        for row in mikrotik.path("/ppp/secret").select().where(name == pppoe_username):
            secret_data.append(row)

        # get specified secret
        secret_id = None
        if len(secret_data) > 0:
            secret_id = secret_data[0].get(".id", None)

        if secret_id:
            # update exist secret
            update_data = {
                ".id": secret_id,
                "disabled": disabled,
            }
            if pppoe_username:
                update_data["name"] = pppoe_username
            if pppoe_password:
                update_data["password"] = pppoe_password

            mikrotik.path("/ppp/secret").update(**update_data)
        else:
            # create new secret data
            package_data = await GetOneData(
                db.packages, {"_id": ObjectId(customer_data.get("id_package", None))}
            )

            if not package_data:
                return False

            insert_data = {
                "name": str(pppoe_username),
                "password": str(pppoe_password),
                "service": "ppp",
                "profile": package_data.get("router_profile", "default"),
                "disabled": disabled,
                "comment": customer_data.get("name", "Undefined"),
            }
            mikrotik.path("/ppp/secret").add(**insert_data)

        if disabled:
            active_data = []
            for row in (
                mikrotik.path("/ppp/active").select().where(name == pppoe_username)
            ):
                active_data.append(row)

            if len(active_data) > 0:
                active_id = active_data[0].get(".id")
                mikrotik.path("/ppp/active").remove(active_id)
    except Exception as e:
        await CreateMikrotikErrorNotification(db, str(e))
        return False

    return True


async def DeleteMikrotikPPPSecret(db, customer_data):
    try:
        id_router = customer_data.get("id_router", None)
        pppoe_username = customer_data.get("pppoe_username", None)

        # check router
        host, username, password, port = await GetMikrotikRouterDataByID(db, id_router)
        if not host:
            return False

        secret_data = []
        secret_id = None
        mikrotik = MikrotikConnection(host, username, password, port)
        name = Key("name")
        for row in mikrotik.path("/ppp/secret").select().where(name == pppoe_username):
            secret_data.append(row)

        if len(secret_data) > 0:
            # remove ppp secret
            secret_id = secret_data[0].get(".id", None)
            mikrotik.path("/ppp/secret").remove(secret_id)

            # remove ppp active
            active_data = []
            for row in (
                mikrotik.path("/ppp/active").select().where(name == pppoe_username)
            ):
                active_data.append(row)

            if len(active_data) > 0:
                active_id = active_data[0].get(".id")
                mikrotik.path("/ppp/active").remove(active_id)
        return True
    except Exception as e:
        await CreateMikrotikErrorNotification(db, str(e))
        return False
