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
    FORBIDDEN_ACCESS_MESSAGE,
    NOT_FOUND_MESSAGE,
    SYSTEM_ERROR_MESSAGE,
)
from fastapi.responses import JSONResponse
from app.models.salary import SalaryInsertData, SalaryStatusData, SalaryUpdateData
from app.models.users import UserData, UserRole
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

router = APIRouter(prefix="/salary", tags=["Salaries"])


@router.get("")
async def get_salaries(
    key: str = None,
    id_user: str = None,
    month: str = None,
    year: str = None,
    status: SalaryStatusData = None,
    page: int = 1,
    items: int = 1,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    query = {}
    if key:
        query["$or"] = [
            {"name": {"$regex": key, "$options": "i"}},
            {"period.month": {"$regex": key, "$options": "i"}},
            {"description": {"$regex": key, "$options": "i"}},
        ]
    if status:
        query["status"] = status
    if id_user:
        query["id_user"] = ObjectId(id_user)
    if month:
        query["period.month"] = month
    if year:
        query["period.year"] = year

    pipeline = [
        {"$match": query},
        {"$sort": {"date": -1}},
        {
            "$lookup": {
                "from": "users",
                "let": {"idUser": "$id_user"},
                "pipeline": [
                    {"$match": {"$expr": {"$eq": ["$_id", "$$idUser"]}}},
                    {"$project": {"name": 1, "email": 1, "phone_number": 1}},
                ],
                "as": "employee",
            }
        },
        {
            "$addFields": {
                "employee": {"$ifNull": [{"$arrayElemAt": ["$employee", 0]}, None]},
            }
        },
    ]

    salary_data, count = await GetManyData(
        db.salary, pipeline, {}, {"page": page, "items": items}
    )
    pagination_info: Pagination = {"page": page, "items": items, "count": count}
    return JSONResponse(
        content={
            "salary_data": salary_data,
            "pagination_info": pagination_info,
        }
    )


@router.post("/add")
async def create_salary(
    data: SalaryInsertData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    payload["id_user"] = ObjectId(payload["id_user"])
    payload["created_at"] = GetCurrentDateTime()
    payload["created_by"] = ObjectId(current_user.id)
    result = await CreateOneData(db.salary, payload)
    if not result.inserted_id:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    if payload["status"] == SalaryStatusData.PAID.value:
        expenditure_data = {
            "id_salary": result.inserted_id,
            "nominal": payload["salary"],
            "category": "GAJI KARYAWAN",
            "method": payload["method"],
            "date": payload["created_at"],
            "description": payload["description"],
            "created_at": GetCurrentDateTime(),
            "created_by": ObjectId(current_user.id),
        }
        await CreateOneData(db.expenditures, expenditure_data)

    return JSONResponse(content={"message": DATA_HAS_INSERTED_MESSAGE})


@router.put("/update/{id}")
async def update_salary(
    id: str,
    data: SalaryUpdateData = Body(..., embed=True),
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    payload = data.dict(exclude_unset=True)
    exist_data = await GetOneData(db.salary, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    if "id_user" in payload and payload["id_user"]:
        payload["id_user"] = ObjectId(payload["id_user"])
    payload["updated_at"] = GetCurrentDateTime()
    payload["updated_by"] = ObjectId(current_user.id)
    result = await UpdateOneData(db.salary, {"_id": ObjectId(id)}, {"$set": payload})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    if (
        "status" in payload
        and payload["status"] == SalaryStatusData.PAID.value
        and exist_data.get("status", None) != payload["status"]
    ):
        expenditure_data = {
            "nominal": payload["salary"],
            "category": "GAJI KARYAWAN",
            "method": exist_data.get("method", None),
            "date": exist_data["created_at"],
            "description": exist_data["description"],
            "created_at": GetCurrentDateTime(),
            "created_by": ObjectId(current_user.id),
        }
        await CreateOneData(db.expenditures, expenditure_data)
    else:
        await UpdateOneData(
            db.expenditures,
            {"id_salary": ObjectId(id)},
            {"$set": {"nominal": payload["salary"]}},
        )
    return JSONResponse(content={"message": DATA_HAS_UPDATED_MESSAGE})


@router.delete("/delete/{id}")
async def delete_salary(
    id: str,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    exist_data = await GetOneData(db.salary, {"_id": ObjectId(id)})
    if not exist_data:
        raise HTTPException(status_code=404, detail={"message": NOT_FOUND_MESSAGE})

    result = await DeleteOneData(db.salary, {"_id": ObjectId(id)})
    if not result:
        raise HTTPException(status_code=500, detail={"message": SYSTEM_ERROR_MESSAGE})

    await DeleteOneData(db.expenditures, {"id_salary": ObjectId(id)})
    return JSONResponse(content={"message": DATA_HAS_DELETED_MESSAGE})
