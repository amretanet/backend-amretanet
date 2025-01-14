from bson import ObjectId
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
)
from app.modules.response_message import (
    DATA_HAS_DELETED_MESSAGE,
    DATA_HAS_INSERTED_MESSAGE,
    DATA_HAS_UPDATED_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from fastapi.responses import JSONResponse
from app.models.change_submissions import (
    ChangeSubmissionInsertData,
    ChangeSubmissionStatusData,
    ChangeSubmissionTypeData,
    ChangeSubmissionUpdateData,
)
from app.models.users import UserData
from app.models.generals import Pagination
from app.modules.generals import GetCurrentDateTime
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import (
    CreateOneData,
    DeleteOneData,
    GetManyData,
    GetOneData,
    UpdateOneData,
)
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase

router = APIRouter(prefix="/change-submission", tags=["Change Submissions"])


@router.get("")
async def get_change_submissions(
    id_customer: str = None,
    key: str = None,
    status: ChangeSubmissionStatusData = None,
    page: int = 1,
    items: int = 10,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}
    if id_customer:
        query["id_customer"] = ObjectId(id_customer)
    if key:
        query["$or"] = [
            {"type": {"$regex": key, "$options": "i"}},
            {"reason_message": {"$regex": key, "$options": "i"}},
            {"confirm_message": {"$regex": key, "$options": "i"}},
        ]
    if status:
        query["status"] = status

    pipeline = [
        {"$match": query},
        {"$sort": {"created_at": -1}},
        {
            "$lookup": {
                "from": "customers",
                "let": {"idCustomer": "$id_customer"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idCustomer"]}}},
                    {"$project": {"name": 1, "service_number": 1}},
                ],
                "as": "customer",
            }
        },
        {"$unwind": {"path": "$customer", "preserveNullAndEmptyArrays": True}},
        {
            "$lookup": {
                "from": "packages",
                "let": {"idPackage": "$id_package"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idPackage"]}}},
                    {"$project": {"name": 1}},
                ],
                "as": "package",
            }
        },
        {"$unwind": {"path": "$package", "preserveNullAndEmptyArrays": True}},
    ]

    change_submission_data, count = await GetManyData(
        db.change_submissions, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "change_submission_data": change_submission_data,
            "pagination_info": pagination_info,
        }
    )


@router.post("/add")
async def create_change_submission(
    data: ChangeSubmissionInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True)
    payload["id_package"] = ObjectId(payload["id_package"])
    payload["id_customer"] = ObjectId(payload["id_customer"])
    payload["status"] = ChangeSubmissionStatusData.PENDING.value
    payload["created_at"] = GetCurrentDateTime()
    result = await CreateOneData(db.change_submissions, payload)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_change_submission(
    id: str,
    data: ChangeSubmissionUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    payload = data.dict(exclude_unset=True, exclude_none=True)
    exist_data = await GetOneData(db.change_submissions, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    request_payload = {
        "id_package": ObjectId(exist_data["id_package"]),
        "id_customer": ObjectId(exist_data["id_customer"]),
    }
    if "id_package" in payload and payload["id_package"]:
        payload["id_package"] = ObjectId(payload["id_package"])
        request_payload["id_package"] = payload["id_package"]
    if "id_customer" in payload:
        payload["id_customer"] = ObjectId(payload["id_customer"])
        request_payload["id_customer"] = payload["id_customer"]
    if "status" in payload and payload["status"] is not None:
        payload["status"] = payload["status"]
    if "reason_message" in payload and payload["reason_message"] is not None:
        payload["reason_message"] = payload["reason_message"]
    if "confirm_message" in payload and payload["confirm_message"] is not None:
        payload["confirmed_at"] = GetCurrentDateTime()
        payload["confirm_message"] = payload["confirm_message"]
    payload["updated_at"] = GetCurrentDateTime()
    result = await UpdateOneData(
        db.change_submissions, {"_id": ObjectId(id)}, {"$set": payload}
    )
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    if (
        payload.get("status")
        and payload.get("status") == ChangeSubmissionStatusData.ACCEPTED
    ):
        request_type = payload["type"] if "type" in payload else exist_data["type"]
        update_data = {}
        if request_type == ChangeSubmissionTypeData.PPPOE:
            update_data = {"$set": {"id_package": request_payload["id_package"]}}
        else:
            update_data = {
                "$addToSet": {"id_add_on_package": request_payload["id_package"]}
            }

        result = await UpdateOneData(
            db.customers, {"_id": request_payload["id_customer"]}, update_data
        )
        if not result:
            raise HTTPException(
                status_code=500, detail={"message": "Gagal Mengubah Data Pelanggan!"}
            )

    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_change_submission(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    exist_data = await GetOneData(db.change_submissions, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.change_submissions, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
