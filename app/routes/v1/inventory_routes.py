from fastapi import APIRouter, Depends, Body, HTTPException
from fastapi.responses import JSONResponse
from bson import ObjectId
from app.models.inventory import (
    InventoryEngineerRequestInsertData,
    InventoryEngineerRequestStatusData,
    InventoryEngineerRequestUpdateStatusData,
    InventoryInsertData,
    InventoryPositionData,
    InventoryProjections,
    InventoryRequestProjections,
)
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    EXIST_DATA_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from app.modules.generals import GetCurrentDateTime
from app.models.users import UserData
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetDistinctData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.routes.v1.auth_routes import GetCurrentUser
from dotenv import load_dotenv

load_dotenv()


router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("")
async def get_inventories(
    key: str = None,
    position: InventoryPositionData = None,
    id_category: str = None,
    page: int = 1,
    items: int = 10,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    pipeline = []
    query = {}
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
        ]
    if id_category:
        query["id_category"] = ObjectId(id_category)
    if position:
        query["position"] = position.value

    pipeline.append({"$match": query})
    pipeline.append(
        {
            "$lookup": {
                "from": "categories",
                "localField": "id_category",
                "foreignField": "_id",
                "as": "category",
            }
        }
    )
    pipeline.append(
        {"$unwind": {"path": "$category", "preserveNullAndEmptyArrays": True}},
    )
    pipeline.append(
        {
            "$sort": {
                "updated_at": -1,
                "created_at": -1,
            }
        }
    )

    if position and position != InventoryPositionData.WAREHOUSE.value:
        pipeline.append(
            {
                "$lookup": {
                    "from": "users",
                    "localField": "id_pic",
                    "foreignField": "_id",
                    "as": "pic",
                }
            }
        )
        pipeline.append(
            {"$unwind": {"path": "$pic", "preserveNullAndEmptyArrays": True}},
        )

    inventory_data, count = await GetManyData(
        db.inventories, pipeline, InventoryProjections, {"page": page, "items": items}
    )
    return JSONResponse(
        content={
            "inventory_data": inventory_data,
            "pagination_info": {"page": page, "items": items, "count": count},
        }
    )


@router.post("/add")
async def create_inventory(
    data: InventoryInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["name"] = str(payload["name"]).strip()
    payload["position"] = InventoryPositionData.WAREHOUSE.value
    exist_query = {
        "name": payload["name"],
        "id_category": ObjectId(payload["id_category"]),
        "position": payload["position"],
    }
    exist_data = await GetOneData(db.inventories, exist_query)
    if exist_data:
        result = await UpdateOneData(
            db.inventories,
            exist_query,
            {
                "$set": {"last_entry": GetCurrentDateTime()},
                "$inc": {"quantity": payload["quantity"]},
            },
        )
        if not result:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )
        return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})
    else:
        payload["id_category"] = ObjectId(payload["id_category"])
        payload["created_at"] = GetCurrentDateTime()
        payload["last_entry"] = GetCurrentDateTime()

        result = await CreateOneData(db.inventories, payload)
        if not result:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_inventory(
    id: str,
    data: InventoryInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.inventories, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    exist_name = await GetOneData(
        db.inventories,
        {
            "_id": {"$ne": ObjectId(id)},
            "name": payload["name"],
            "id_category": ObjectId(payload["id_category"]),
            "position": InventoryPositionData.WAREHOUSE.value,
        },
    )
    if exist_name:
        raise HTTPException(status_code=400, detail={"message": EXIST_DATA_MESSAGE})

    exist_stock = exist_data.get("quantity", 0)
    current_stock = payload.get("quantity", 0)
    if current_stock < exist_stock:
        payload["last_out"] = GetCurrentDateTime()
    elif current_stock > exist_stock:
        payload["last_entry"] = GetCurrentDateTime()

    payload["id_category"] = ObjectId(payload["id_category"])
    payload["updated_at"] = GetCurrentDateTime()

    result = await UpdateOneData(
        db.inventories, {"_id": ObjectId(id)}, {"$set": payload}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_inventory(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.inventories, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.inventories, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})


@router.get("/requested")
async def get_inventory_engineer_request(
    key: str = None,
    status: InventoryEngineerRequestStatusData = None,
    id_engineer: str = None,
    page: int = 1,
    items: int = 10,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    pipeline = []
    query = {}
    if key:
        inventory_ids = await GetDistinctData(
            db.inventories, {"name": {"$regex": key, "$options": "i"}}
        )
        if len(inventory_ids) > 0:
            inventory_ids = [ObjectId(item) for item in inventory_ids]
            query["id_inventory"] = {"$in": inventory_ids}

    if id_engineer:
        query["id_engineer"] = ObjectId(id_engineer)
    if status:
        query["status"] = status.value

    pipeline.append({"$match": query})
    pipeline.append(
        {
            "$lookup": {
                "from": "users",
                "localField": "id_engineer",
                "foreignField": "_id",
                "as": "engineer",
            }
        }
    )
    pipeline.append(
        {"$unwind": {"path": "$engineer", "preserveNullAndEmptyArrays": True}},
    )
    pipeline.append(
        {
            "$lookup": {
                "from": "inventories",
                "localField": "id_inventory",
                "foreignField": "_id",
                "as": "inventory",
            }
        }
    )
    pipeline.append(
        {"$unwind": {"path": "$inventory", "preserveNullAndEmptyArrays": True}},
    )
    pipeline.append({"$sort": {"created_at": -1}})

    inventory_requested_data, count = await GetManyData(
        db.inventory_requested,
        pipeline,
        InventoryRequestProjections,
        {"page": page, "items": items},
    )
    return JSONResponse(
        content={
            "inventory_requested_data": inventory_requested_data,
            "pagination_info": {"page": page, "items": items, "count": count},
        }
    )


@router.post("/requested/add")
async def add_inventory_engineer_request(
    data: InventoryEngineerRequestInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict()
    payload["id_engineer"] = ObjectId(payload["id_engineer"])
    payload["id_inventory"] = ObjectId(payload["id_inventory"])
    payload["status"] = InventoryEngineerRequestStatusData.PENDING.value
    exist_inventory = await GetOneData(db.inventories, {"_id": payload["id_inventory"]})
    if not exist_inventory:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    if exist_inventory.get("quantity", 0) < payload.get("quantity", 0):
        raise HTTPException(
            status_code=400, detail={"message": "Jumlah Stok Gudang Tidak Tersedia!"}
        )

    exist_request = await GetOneData(
        db.inventory_requested,
        {
            "id_inventory": payload["id_inventory"],
            "id_engineer": payload["id_engineer"],
            "status": payload["status"],
        },
    )
    if exist_request:
        raise HTTPException(
            status_code=400, detail={"message": "Proses Masih Dalam Pengajuan!"}
        )

    payload["created_at"] = GetCurrentDateTime()
    result = await CreateOneData(db.inventory_requested, payload)
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/requested/update/{id}")
async def update_inventory_engineer_request(
    id: str,
    data: InventoryEngineerRequestInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.inventory_requested, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    payload = data.dict()
    payload["id_engineer"] = ObjectId(payload["id_engineer"])
    payload["id_inventory"] = ObjectId(payload["id_inventory"])
    exist_inventory = await GetOneData(db.inventories, {"_id": payload["id_inventory"]})
    if not exist_inventory:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    if exist_inventory.get("quantity", 0) < payload.get("quantity", 0):
        raise HTTPException(
            status_code=400, detail={"message": "Jumlah Stok Gudang Tidak Tersedia!"}
        )

    exist_request = await GetOneData(
        db.inventory_requested,
        {
            "_id": {"$ne": ObjectId(id)},
            "id_inventory": payload["id_inventory"],
            "id_engineer": payload["id_engineer"],
            "status": InventoryEngineerRequestStatusData.PENDING.value,
        },
    )
    if exist_request:
        raise HTTPException(
            status_code=400, detail={"message": "Proses Masih Dalam Pengajuan!"}
        )

    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(
        db.inventory_requested, {"_id": ObjectId(id)}, {"$set": payload}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.put("/requested/update-status/{id}")
async def update_inventory_engineer_request_status(
    id: str,
    data: InventoryEngineerRequestUpdateStatusData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.inventory_requested, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    id_inventory = ObjectId(exist_data.get("id_inventory"))
    exist_inventory = await GetOneData(db.inventories, {"_id": id_inventory})
    if not exist_inventory:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    if exist_inventory.get("quantity", 0) < exist_data.get("quantity", 0):
        raise HTTPException(
            status_code=400, detail={"message": "Jumlah Stok Gudang Tidak Tersedia!"}
        )

    payload = data.dict()
    if payload["status"] == InventoryEngineerRequestStatusData.ACCEPTED.value:
        insert_data = {
            "name": exist_inventory.get("name"),
            "id_category": ObjectId(exist_inventory.get("id_category")),
            "quantity": exist_data.get("quantity", 0),
            "unit": exist_inventory.get("unit"),
            "description": exist_inventory.get("description"),
            "position": InventoryPositionData.ENGINEER.value,
            "id_pic": ObjectId(exist_data.get("id_engineer")),
            "created_at": GetCurrentDateTime(),
        }
        exist_engineer_query = {
            "name": insert_data["name"],
            "id_category": insert_data["id_category"],
            "id_pic": insert_data["id_pic"],
        }
        exist_engineer_data = await GetOneData(db.inventories, exist_engineer_query)
        if exist_engineer_data:
            result = await UpdateOneData(
                db.inventories,
                exist_engineer_query,
                {"$inc": {"quantity": insert_data["quantity"]}},
            )
        else:
            result = await CreateOneData(db.inventories, insert_data)

        if not result:
            raise HTTPException(
                status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE}
            )

        await UpdateOneData(
            db.inventories,
            {"_id": ObjectId(exist_inventory.get("_id"))},
            {
                "$inc": {"quantity": exist_data.get("quantity", 0) * -1},
                "$set": {"last_out": GetCurrentDateTime()},
            },
        )

    result = await UpdateOneData(
        db.inventory_requested,
        {"_id": ObjectId(id)},
        {
            "$set": {
                "status": payload["status"],
            }
        },
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/requested/delete/{id}")
async def delete_inventory_engineer_request(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.inventory_requested, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.inventory_requested, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
