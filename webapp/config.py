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
# BikeTracker-Quelle: "drive" (Google Drive API mit Dienstkonto) oder "local" (Verzeichnis)
BIKETRACKER_SOURCE = "drive"
BIKETRACKER_DIR = r"G:\Meine Ablage\BikeTracker"
BIKETRACKER_DRIVE_KEY_FILE = str(PROJECT_ROOT / "secrets" / "biketracker-service-account.json")
BIKETRACKER_DRIVE_FOLDER_NAME = "BikeTracker"
# Optional: Ordner-ID aus der Drive-URL; leer = Suche über BIKETRACKER_DRIVE_FOLDER_NAME
BIKETRACKER_DRIVE_FOLDER_ID = ""
BIKETRACKER_MAX_FILES = 10
# Unterordner, in den "Löschen" auf der BikeTracker-Seite die Dateien verschiebt
BIKETRACKER_DELETED_FOLDER_NAME = "Gelöscht"
# Unterordner mit den Tourbildern/-videos (Tabelle media) für die Tourbilder-Seite
BIKETRACKER_IMAGES_FOLDER_NAME = "images"

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
    BIKETRACKER_SOURCE = BIKETRACKER_SOURCE
    BIKETRACKER_DIR = BIKETRACKER_DIR
    BIKETRACKER_DRIVE_KEY_FILE = BIKETRACKER_DRIVE_KEY_FILE
    BIKETRACKER_DRIVE_FOLDER_NAME = BIKETRACKER_DRIVE_FOLDER_NAME
    BIKETRACKER_DRIVE_FOLDER_ID = BIKETRACKER_DRIVE_FOLDER_ID
    BIKETRACKER_MAX_FILES = BIKETRACKER_MAX_FILES
    BIKETRACKER_DELETED_FOLDER_NAME = BIKETRACKER_DELETED_FOLDER_NAME
    BIKETRACKER_IMAGES_FOLDER_NAME = BIKETRACKER_IMAGES_FOLDER_NAME

    GOAL_UI_TO_DB_KEY = GOAL_UI_TO_DB_KEY
    VALID_GOAL_DB_KEYS = VALID_GOAL_DB_KEYS
    ACTIVITY_TYPE_ALIASES = ACTIVITY_TYPE_ALIASES
    MONTH_NAMES = MONTH_NAMES
