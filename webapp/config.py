import os
from pathlib import Path

WEBAPP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = WEBAPP_ROOT.parent

DB_CONFIG = {
    "user": "root",
    "password": "hurtzming",
    "host": "127.0.0.1",
    "database": "tourbook",
    "allow_local_infile": True,
}

GPX_BASE_PATH = r"C:\ProgramData\MySQL\MySQL Server 8.0\Uploads"
GPX_IMPORT_TARGET_DIR = os.path.join(GPX_BASE_PATH, "activities")
UPLOAD_TMP_DIR = str(PROJECT_ROOT / "uploads_tmp")
VENDOR_STATIC_DIR = str(PROJECT_ROOT / "static" / "vendor")

GOAL_UI_TO_DB_KEY = {
    "annual": "goal_km_year",
    "monthly": "monthly",
    "weekly": "weekly",
    "daily": "daily",
}

VALID_GOAL_DB_KEYS = set(GOAL_UI_TO_DB_KEY.values())

ACTIVITY_TYPE_ALIASES = {
    "per pedes": "hiking",
}

MONTH_NAMES = (
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
)


class Config:
    PROJECT_ROOT = str(PROJECT_ROOT)
    WEBAPP_ROOT = str(WEBAPP_ROOT)

    DB_CONFIG = DB_CONFIG

    GPX_BASE_PATH = GPX_BASE_PATH
    GPX_IMPORT_TARGET_DIR = GPX_IMPORT_TARGET_DIR
    UPLOAD_TMP_DIR = UPLOAD_TMP_DIR
    VENDOR_STATIC_DIR = VENDOR_STATIC_DIR

    GOAL_UI_TO_DB_KEY = GOAL_UI_TO_DB_KEY
    VALID_GOAL_DB_KEYS = VALID_GOAL_DB_KEYS
    ACTIVITY_TYPE_ALIASES = ACTIVITY_TYPE_ALIASES
    MONTH_NAMES = MONTH_NAMES

STRAVA_CLIENT_ID=232044
STRAVA_CLIENT_SECRET="709ef76e5923c55e37389c53bbdf91eee387a43e"