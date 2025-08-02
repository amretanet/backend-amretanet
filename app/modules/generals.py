from calendar import monthrange
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
from urllib.parse import urlparse
from bson import ObjectId
import pytz
from typing import Any
import secrets
import string
from app.modules.crud_operations import GetDistinctData
from dotenv import load_dotenv

load_dotenv()


def NumberToWords(number: int) -> str:
    satuan = [
        "",
        "Satu",
        "Dua",
        "Tiga",
        "Empat",
        "Lima",
        "Enam",
        "Tujuh",
        "Delapan",
        "Sembilan",
    ]
    levels = ["", "Ribu", "Juta", "Milyar", "Triliun"]

    if number == 0:
        return "Nol"

    result = ""
    level = 0

    while number > 0:
        part = number % 1000

        if part != 0:
            part_str = ""
            ratusan = part // 100
            puluhan_dan_satuan = part % 100

            if ratusan > 0:
                part_str += "Seratus " if ratusan == 1 else f"{satuan[ratusan]} Ratus "

            if puluhan_dan_satuan > 0:
                if puluhan_dan_satuan < 10:
                    part_str += f"{satuan[puluhan_dan_satuan]} "
                elif puluhan_dan_satuan == 10:
                    part_str += "Sepuluh "
                elif puluhan_dan_satuan < 20:
                    if puluhan_dan_satuan == 11:
                        part_str += "Sebelas "
                    else:
                        part_str += f"{satuan[puluhan_dan_satuan % 10]} Belas "
                else:
                    puluhan = puluhan_dan_satuan // 10
                    satuan_angka = puluhan_dan_satuan % 10

                    part_str += f"{satuan[puluhan]} Puluh "
                    if satuan_angka > 0:
                        part_str += f"{satuan[satuan_angka]} "

            if level == 1 and part == 1:
                part_str = "Seribu "
            else:
                part_str += f"{levels[level]} "

            result = part_str + result

        level += 1
        number //= 1000

    return result.strip()


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


async def GenerateUniqueCode(db):
    used_unique_code = await GetDistinctData(db.customers, {}, "unique_code")
    last_unique_code = 0
    if len(used_unique_code) > 0:
        last_unique_code = max(used_unique_code)

    new_unique_code = last_unique_code + 1
    while new_unique_code % 10 == 0:
        new_unique_code += 1

    return new_unique_code


def GenerateRandomString(unique_data, length: int = 10):
    alphabet = string.ascii_letters + string.digits
    random_string = "".join(secrets.choice(alphabet) for _ in range(length))
    return random_string.lower()


def GetDueDateRange(gap: int):
    current_date = GetCurrentDateTime()
    target_date = current_date + timedelta(days=gap)

    current_year = current_date.year
    current_month = current_date.month
    current_day = current_date.day

    target_month = target_date.month
    target_day = target_date.day
    last_day_of_current_month = monthrange(current_year, current_month)[1]

    if target_month == current_month:
        current_month_dates = [
            str(day).zfill(2) for day in range(current_day, target_day + 1)
        ]
        next_month_dates = []
    else:
        current_month_dates = [
            str(day).zfill(2)
            for day in range(current_day, last_day_of_current_month + 1)
        ]
        next_month_dates = [str(day).zfill(2) for day in range(1, target_day + 1)]

    if len(current_month_dates) > 0:
        last_current_date = int(current_month_dates[-1])
        if len(next_month_dates) > 0:
            for last_current_date in range(last_current_date + 1, 32):
                current_month_dates.append(str(last_current_date).zfill(2))

    return current_month_dates, next_month_dates


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
