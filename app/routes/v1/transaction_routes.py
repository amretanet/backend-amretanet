from datetime import datetime
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from app.modules.response_message import FORBIDDEN_ACCESS_MESSAGE
from fastapi.responses import JSONResponse, StreamingResponse
from app.models.users import UserData, UserRole
from app.routes.v1.auth_routes import GetCurrentUser
from app.modules.crud_operations import GetAggregateData
from app.modules.database import AsyncIOMotorClient, GetAmretaDatabase
from app.modules.generals import GetCurrentDateTime, NumberToWords
from app.modules.pdf import CreateCashflowPDF


router = APIRouter(prefix="/transaction", tags=["Transactions"])


@router.get("/cashflow")
async def get_cashflow(
    from_date: datetime = None,
    to_date: datetime = None,
    current_user: UserData = Depends(GetCurrentUser),
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    if current_user.role == UserRole.CUSTOMER:
        raise HTTPException(
            status_code=403, detail={"message": FORBIDDEN_ACCESS_MESSAGE}
        )
    query = {}

    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}

    pipeline = [
        {"$match": query},
        {"$sort": {"date": 1}},
    ]

    incomes_data = await GetAggregateData(
        db.incomes,
        pipeline,
        {
            "category": 1,
            "date": {"$dateToString": {"format": "%Y-%m-%d %H:%M:%S", "date": "$date"}},
            "description": 1,
            "method": 1,
            "credit": "$nominal",
            "type": "INCOMES",
        },
    )
    expenditures_data = await GetAggregateData(
        db.expenditures,
        pipeline,
        {
            "category": 1,
            "date": {"$dateToString": {"format": "%Y-%m-%d %H:%M:%S", "date": "$date"}},
            "description": 1,
            "method": 1,
            "debit": "$nominal",
            "type": "EXPENDITURES",
        },
    )

    cashflow_data = incomes_data + expenditures_data
    cashflow_data = sorted(
        cashflow_data,
        key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d %H:%M:%S"),
    )
    saldo_count = 0
    for entry in cashflow_data:
        if entry["type"] == "INCOMES":
            saldo_count += entry.get("credit", 0)
        elif entry["type"] == "EXPENDITURES":
            saldo_count -= entry.get("debit", 0)

        entry["saldo"] = saldo_count

    return JSONResponse(
        content={
            "cashflow_data": cashflow_data,
            "saldo_count": saldo_count,
        }
    )


@router.get("/cashflow/pdf")
async def print_cashflow_pdf(
    from_date: datetime = None,
    to_date: datetime = None,
    db: AsyncIOMotorClient = Depends(GetAmretaDatabase),
):
    query = {}

    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}

    pipeline = [
        {"$match": query},
        {"$sort": {"date": 1}},
    ]

    incomes_data = await GetAggregateData(
        db.incomes,
        pipeline,
        {
            "category": 1,
            "date": {"$dateToString": {"format": "%Y-%m-%d %H:%M:%S", "date": "$date"}},
            "description": 1,
            "method": 1,
            "credit": "$nominal",
            "type": "INCOMES",
        },
    )
    expenditures_data = await GetAggregateData(
        db.expenditures,
        pipeline,
        {
            "category": 1,
            "date": {"$dateToString": {"format": "%Y-%m-%d %H:%M:%S", "date": "$date"}},
            "description": 1,
            "method": 1,
            "debit": "$nominal",
            "type": "EXPENDITURES",
        },
    )

    cashflow_data = incomes_data + expenditures_data
    cashflow_data = sorted(
        cashflow_data,
        key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d %H:%M:%S"),
    )
    saldo_count = 0
    for entry in cashflow_data:
        if entry["type"] == "INCOMES":
            saldo_count += entry.get("credit", 0)
        elif entry["type"] == "EXPENDITURES":
            saldo_count -= entry.get("debit", 0)

        entry["saldo"] = saldo_count

    pdf_bytes = CreateCashflowPDF(cashflow_data, from_date, to_date, saldo_count)
    file_name = f"Laporan Rekapitulasi Keuangan-{GetCurrentDateTime().timestamp()}.pdf"
    return StreamingResponse(
        pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={file_name}"},
    )
