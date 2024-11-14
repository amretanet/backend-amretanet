from datetime import datetime
from dateutil.relativedelta import relativedelta
from bson import ObjectId
import pytz
from typing import Any
import os
from dotenv import load_dotenv
import requests

load_dotenv()

BE_WEBSOCKET = os.getenv("BE_WEBSOCKET")


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


def GetPrevFromToDate(from_date: datetime, to_date: datetime):
    time_diff = to_date - from_date
    new_to_date = from_date - relativedelta(seconds=1)
    new_from_date = new_to_date - time_diff
    return new_from_date, new_to_date


def GetGrowthPercentage(before_value, current_value):
    growth_type = "up"
    difference = current_value - before_value
    if difference < 0:
        growth_type = "down"
    elif difference == 0:
        growth_type = "flat"

    if before_value == 0 and current_value == 0:
        return 0, growth_type
    elif before_value == 0:
        return 100, growth_type

    percentage = (difference / before_value) * 100

    return round(abs(percentage), 2), growth_type


def ResponseFormatter(data={}, message: str = "", success: bool = False):
    response = {
        "data": data,
        "message": message,
        "success": success,
    }
    return response


def SetEnumDescriptionData(class_data):
    tmp_source = list(class_data.__members__.items())
    list_data = []
    for key, value in tmp_source:
        temp = f"({value.value} : {key})"
        list_data.append(temp)

    return ", ".join(list_data)


def SendNotification(db, data):
    result = db.notifications.insert_one(data)
    data["id"] = str(result.inserted_id)
    del data["_id"]
    data["created_at"] = str(data["created_at"])
    requests.post(f"{BE_WEBSOCKET}/sma/send-notif-export", json=data)
