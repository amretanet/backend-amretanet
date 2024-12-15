from pydantic import BaseModel
from enum import Enum


# schemas
class IncomeCategoryData(str, Enum):
    INVOICE_PAYMENT = "BAYAR TAGIHAN"
    CASH_RECEIPT = "KASBON"
    TOP_UP = "TOP UP"
    TRANSFER = "TRANSFER"
    PURCHASE = "PEMBELIAN ALAT"
    SALARY = "GAJI KARYAWAN"
    INVESTMENT = "INVESTASI"
