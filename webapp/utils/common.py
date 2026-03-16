import os
from datetime import date, datetime

from ..config import ACTIVITY_TYPE_ALIASES


def get_db_type(filter_type):
    if filter_type == "Alle" or not filter_type:
        return None
    return ACTIVITY_TYPE_ALIASES.get(filter_type, filter_type)


def format_date_display(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return str(value)


def format_duration_hm(elapsed_time_s):
    duration_s = elapsed_time_s or 0
    hours = int(duration_s // 3600)
    minutes = int((duration_s % 3600) // 60)
    return f"{hours:02d}:{minutes:02d}"


def parse_month_year(month_value, year_value):
    try:
        return int(month_value), int(year_value)
    except (TypeError, ValueError):
        today = date.today()
        return today.month, today.year


def build_gpx_path(base_path, filename):
    if not filename:
        return ""
    return os.path.join(base_path, filename.replace("/", os.sep))