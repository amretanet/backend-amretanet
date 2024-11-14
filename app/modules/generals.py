from datetime import datetime
from bson import ObjectId
import pytz
from typing import Any
import os
from dotenv import load_dotenv

load_dotenv()


def JsonObjectFormatter(obj: Any):
    if isinstance(obj, ObjectId):
        return str(obj)

    if isinstance(obj, datetime):
        return str(obj)

    raise TypeError("%r is not JSON serializable" % obj)


def GetCurrentDateTime():
    to_zone = pytz.timezone("Asia/Jakarta")
    current_time = datetime.now(to_zone).replace(tzinfo=None)

    return current_time


def DateTimeFormatter(date: str):
    return date.strftime("%d %B %Y %H:%M:%S")


def DateTimeValidator(date: str):
    try:
        date_convert = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")
        return date_convert
    except ValueError:
        return False


def DateTimeCompare(first_date, second_date):
    first_datetime = DateTimeValidator(first_date)
    second_datetime = DateTimeValidator(second_date)

    if first_datetime is None or second_datetime is None:
        return False
    return first_datetime < second_datetime


def ObjectIDValidator(id: str):
    try:
        object_id = ObjectId(id)
        return object_id
    except Exception:
        return False


def ResponseFormatter(data={}, message: str = "", success: bool = False):
    response = {
        "data": data,
        "message": message,
        "success": success,
    }
    return response



