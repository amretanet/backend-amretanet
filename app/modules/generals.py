from datetime import datetime, timedelta
from bson import ObjectId
import pytz
from typing import Any
from dotenv import load_dotenv

load_dotenv()


def AddURLHTTPProtocol(url):
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    return url


def ReminderDateFormatter(due_date):
    current_year = datetime.now().year
    current_month = datetime.now().month
    try:
        full_due_date = datetime(
            year=current_year, month=current_month, day=int(due_date)
        )
        five_days_before = full_due_date - timedelta(days=5)
        return five_days_before.strftime("%d")
    except ValueError:
        return None


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
