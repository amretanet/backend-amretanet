from bson import ObjectId
from fastapi import APIRouter, Depends, Body, HTTPException
from fastapi.responses import JSONResponse
from app.modules.crud_operations import (
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
    CreateOneData,
)
from app.models.generals import Pagination
from app.models.users import (
    UserData,
    UserRole,
)
from app.models.referral_fees import (
    ReferralFeeInsertData,
    ReferralFeeProjections,
    ReferralFeeRequestData,
    ReferralFeeStatusData,
    ReferralFeeUpdateData,
    ReferralFeeUserProjections,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import (
    GetCurrentDateTime,
    ObjectIDValidator,
)
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    FORBIDDEN_ACCESS_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
    OBJECT_ID_NOT_VALID_MESSAGE,
)
from app.routes.v1.auth_routes import GetCurrentUser
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/referral-fee", tags=["Referral Fees"])


@router.get("")
async def get_referral_fees(
    key: str = None,
    status: ReferralFeeStatusData = None,
    id_user: str = None,
    page: int = 1,
    items: int = 10,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )

    query = {}
    if key:
        query = {
            "$or": [
                {"description": {"$regex": key, "$options": "i"}},
                {"reason": {"$regex": key, "$options": "i"}},
            ]
        }
    if status:
        query["status"] = status.value
    if id_user:
        id_user = ObjectIDValidator(id_user)
        if not id_user:
            raise HTTPException(
                status_code=400, detail={"message": OBJECT_ID_NOT_VALID_MESSAGE}
            )

        query["id_user"] = id_user

    pipeline = [
        {"$match": query},
        {
            "$addFields": {
                "status_priority": {
                    "$switch": {
                        "branches": [
                            {
                                "case": {
                                    "$eq": [
                                        "$status",
                                        ReferralFeeStatusData.PENDING.value,
                                    ]
                                },
                                "then": 1,
                            },
                            {
                                "case": {
                                    "$eq": [
                                        "$status",
                                        ReferralFeeStatusData.ACCEPTED.value,
                                    ]
                                },
                                "then": 2,
                            },
                        ],
                        "default": 3,
                    }
                }
            }
        },
        {"$sort": {"status_priority": 1, "created_at": -1, "updated_at": -1}},
        {
            "$lookup": {
                "from": "users",
                "localField": "id_user",
                "foreignField": "_id",
                "as": "user_data",
            }
        },
        {"$unwind": "$user_data"},
    ]
    referral_fee_data, count = await GetManyData(
        db.referral_fees,
        pipeline,
        ReferralFeeProjections,
        {"page": page, "items": items},
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}

    return JSONResponse(
        content={
            "referral_fee_data": referral_fee_data,
            "pagination_info": pagination_info,
        }
    )


@router.get("/users")
async def get_referral_fee_users(
    key: str = None,
    role: UserRole = UserRole.MITRA,
    page: int = 1,
    items: int = 10,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )

    query = {}
    if key:
        query = {
            "$or": [
                {"name": {"$regex": key, "$options": "i"}},
                {"email": {"$regex": key, "$options": "i"}},
                {"phone_number": {"$regex": key, "$options": "i"}},
                {"referral": {"$regex": key, "$options": "i"}},
            ]
        }
    if role:
        query["role"] = role

    pipeline = [
        {"$match": query},
        {"$sort": {"role": 1, "name": 1}},
    ]
    pipeline.append(
        {
            "$lookup": {
                "from": "customers",
                "localField": "referral",
                "foreignField": "referral",
                "as": "customer_data",
            }
        }
    )
    pipeline.append({"$addFields": {"customer_count": {"$size": "$customer_data"}}})

    user_data, count = await GetManyData(
        db.users, pipeline, ReferralFeeUserProjections, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}

    return JSONResponse(
        content={"user_data": user_data, "pagination_info": pagination_info}
    )


@router.post("/add")
async def add_referral_fee(
    data: ReferralFeeInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )

    payload = data.dict(exclude_unset=True)
    if payload["nominal"] <= 0:
        raise HTTPException(
            status_code=400,
            detail={"message": "Jumlah Nominal Tidak Boleh Kurang Dari Nol!"},
        )

    id_user = ObjectIDValidator(payload["id_user"])
    if not id_user:
        raise HTTPException(
            status_code=400, detail={"message": OBJECT_ID_NOT_VALID_MESSAGE}
        )

    user_data = await GetOneData(db.users, {"_id": id_user})
    if user_data.get("saldo", 0) < payload["nominal"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Jumlah Saldo Tidak Mencukupi Untuk Melakukan Penarikan!"
            },
        )

    payload["id_user"] = id_user
    payload["created_at"] = GetCurrentDateTime()
    payload["created_by"] = ObjectId(current_user.id)
    payload["status"] = ReferralFeeStatusData.ACCEPTED
    result = await CreateOneData(db.referral_fees, payload)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})
    current_saldo = user_data["saldo"] - payload["nominal"]
    user_result = await UpdateOneData(
        db.users,
        {"_id": id_user},
        {"$set": {"saldo": current_saldo}},
    )
    if not user_result:
        await DeleteOneData(db.referral_fees, {"_id": result.inserted_id})
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    payload["category"] = "BONUS MITRA"
    payload["id_referral_fee"] = result.inserted_id
    del payload["status"]
    await CreateOneData(db.expenditures, payload)

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.post("/request")
async def request_referral_fee(
    data: ReferralFeeRequestData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )

    payload = data.dict(exclude_unset=True)
    if payload["nominal"] <= 0:
        raise HTTPException(
            status_code=400,
            detail={"message": "Jumlah Nominal Tidak Boleh Kurang Dari Nol!"},
        )

    id_user = ObjectIDValidator(payload["id_user"])
    if not id_user:
        raise HTTPException(
            status_code=400, detail={"message": OBJECT_ID_NOT_VALID_MESSAGE}
        )

    user_data = await GetOneData(db.users, {"_id": id_user})
    if user_data.get("saldo", 0) < payload["nominal"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Jumlah Saldo Tidak Mencukupi Untuk Melakukan Penarikan!"
            },
        )
    payload["id_user"] = id_user
    payload["created_at"] = GetCurrentDateTime()
    payload["created_by"] = ObjectId(current_user.id)
    payload["status"] = ReferralFeeStatusData.PENDING
    result = await CreateOneData(db.referral_fees, payload)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_referral_fee(
    id: str,
    data: ReferralFeeUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_referral_fees = await GetOneData(db.referral_fees, {"_id": ObjectId(id)})
    if not exist_referral_fees:
        raise HTTPException(status_code=400, detail={"message": NOT_FOUND_MESSAGE})

    payload = data.dict(exclude_unset=True, exclude_none=True)
    payload["updated_at"] = GetCurrentDateTime()

    if "status" in payload and payload["status"] == ReferralFeeStatusData.ACCEPTED:
        user_data = await GetOneData(
            db.users, {"_id": ObjectId(exist_referral_fees["id_user"])}
        )
        if user_data.get("saldo", 0) < payload["nominal"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Jumlah Saldo Tidak Mencukupi Untuk Melakukan Penarikan!"
                },
            )
        payload["accepted_at"] = GetCurrentDateTime()
        payload["accepted_by"] = ObjectId(current_user.id)
    if "status" in payload and payload["status"] == ReferralFeeStatusData.REJECTED:
        payload["rejected_at"] = GetCurrentDateTime()
        payload["rejected_by"] = ObjectId(current_user.id)

    result = await UpdateOneData(
        db.referral_fees, {"_id": ObjectId(id)}, {"$set": payload}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    if "status" in payload and payload["status"] == ReferralFeeStatusData.ACCEPTED:
        current_saldo = user_data["saldo"] - payload["nominal"]
        await UpdateOneData(
            db.users,
            {"_id": ObjectId(exist_referral_fees["id_user"])},
            {"$set": {"saldo": current_saldo}},
        )
        payload["category"] = "BONUS MITRA"
        payload["id_referral_fee"] = ObjectId(id)
        del payload["status"]
        await CreateOneData(db.expenditures, payload)

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_referral_fee(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    exist_referral_fee = await GetOneData(db.referral_fees, {"_id": ObjectId(id)})
    if not exist_referral_fee:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.referral_fees, {"_id": ObjectId(id)})
    if not result.deleted_count:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
