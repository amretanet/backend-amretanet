from datetime import datetime, timedelta
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from bson import ObjectId
import pytz
from typing import Any
from dotenv import load_dotenv

load_dotenv()


def RemoveFilePath(file_path: str):
    parsed_url = urlparse(file_path)
    static_path = parsed_url.path
    file_path = Path(static_path.lstrip("/"))
    file = Path(file_path)
    if file.exists() and file.is_file():
        file.unlink()

    return "File Telah Dihapus!"


def GenerateReferralCode(unique_data):
    referral_code = hashlib.md5(unique_data.encode())
    return referral_code.hexdigest()[:10].upper()


def GetDueDateRange(gap: int):
    current_date = GetCurrentDateTime()
    target_date = current_date + timedelta(days=gap)

    current_day = current_date.day
    target_day = target_date.day

    if current_day <= target_day:
        date_range = [str(day).zfill(2) for day in range(current_day, target_day + 1)]
    else:
        date_range = [str(day).zfill(2) for day in range(target_day, current_day + 1)]

    return date_range


def DateIDFormatter(date, is_show_time: bool = False):
    if date is None:
        return "-"

    month_mapping = {
        1: "Januari",
        2: "Februari",
        3: "Maret",
        4: "April",
        5: "Mei",
        6: "Juni",
        7: "Juli",
        8: "Agustus",
        9: "September",
        10: "Oktober",
        11: "November",
        12: "Desember",
    }

    # Parsing tanggal
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        parsed_date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S")

    # Format tanggal
    date_part = (
        f"{parsed_date.day:02d} {month_mapping[parsed_date.month]} {parsed_date.year}"
    )
    if is_show_time:
        time_part = (
            f"{parsed_date.hour:02d}:{parsed_date.minute:02d}:{parsed_date.second:02d}"
        )
        return f"{date_part} {time_part}"

    return date_part


def ThousandSeparator(number):
    return f"{number:,}".replace(",", ".")


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
