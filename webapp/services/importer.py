import os
import shutil

from flask import current_app, has_app_context

from ..config import GPX_IMPORT_TARGET_DIR
from ..db.database import get_db_connection
from .track_files import parse_track_file, track_extension

# Toleranz für den Streckenvergleich bei der Duplikatprüfung
DUPLICATE_DISTANCE_TOLERANCE_KM = 0.01


class DuplicateActivityError(ValueError):
    """Die Tour ist bereits vorhanden (gleiche Startzeit und Strecke)."""

    def __init__(self, activity_id: int, activity_name: str):
        self.activity_id = activity_id
        self.activity_name = activity_name
        super().__init__(f"Tour bereits vorhanden: '{activity_name}' (ID {activity_id})")


def _get_target_dir():
    if has_app_context():
        return current_app.config.get("GPX_IMPORT_TARGET_DIR", GPX_IMPORT_TARGET_DIR)
    return GPX_IMPORT_TARGET_DIR


# Spalten, die beim Import aus der Tourdatei befüllt werden; fehlende Werte bleiben NULL
INSERT_COLUMNS = (
    "activity_date",
    "activity_name",
    "activity_type",
    "elapsed_time_s",
    "distance_km",
    "elevation_gain_m",
    "min_elevation_m",
    "max_elevation_m",
    "temp_min_c",
    "temp_max_c",
    "avg_watts",
    "max_watts",
    "calories",
    "moving_time_s",
    "max_speed_kmh",
    "avg_cadence_rpm",
    "max_cadence_rpm",
    "avg_heart_rate_bpm",
    "max_heart_rate_bpm",
    "device_name",
)


def insert_activity(conn, data: dict) -> int:
    sql = f"""
        INSERT INTO activities ({", ".join(INSERT_COLUMNS)}, filename)
        VALUES ({", ".join(["%s"] * len(INSERT_COLUMNS))}, NULL)
    """

    cur = conn.cursor()
    try:
        cur.execute(sql, tuple(data.get(column) for column in INSERT_COLUMNS))
        activity_id = cur.lastrowid
        conn.commit()
        return int(activity_id)
    finally:
        cur.close()


def update_filename(conn, activity_id: int, filename: str) -> None:
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE activities SET filename = %s WHERE activity_id = %s",
            (filename, activity_id),
        )
        conn.commit()
    finally:
        cur.close()


def delete_activity(conn, activity_id: int) -> None:
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM activities WHERE activity_id = %s", (activity_id,))
        conn.commit()
    finally:
        cur.close()


def find_duplicate(conn, data: dict):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT activity_id, activity_name
            FROM activities
            WHERE activity_date = %s
              AND ABS(distance_km - %s) < %s
            LIMIT 1
            """,
            (data["activity_date"], data["distance_km"], DUPLICATE_DISTANCE_TOLERANCE_KM),
        )
        return cur.fetchone()
    finally:
        cur.close()


def process_track_file(file_path: str, filename: str = None) -> int:
    """Importiert eine GPX- oder TCX-Datei; das Format ergibt sich aus der Endung von filename bzw. file_path."""
    track_data = parse_track_file(file_path, filename)
    extension = track_extension(filename or file_path)
    target_dir = _get_target_dir()
    os.makedirs(target_dir, exist_ok=True)

    conn = get_db_connection()
    try:
        duplicate = find_duplicate(conn, track_data)
        if duplicate:
            raise DuplicateActivityError(int(duplicate[0]), duplicate[1])

        activity_id = insert_activity(conn, track_data)

        new_filename = f"activities/{activity_id}{extension}"
        target_path = os.path.join(target_dir, f"{activity_id}{extension}")

        try:
            shutil.copy2(file_path, target_path)
            update_filename(conn, activity_id, new_filename)
        except Exception:
            # Keinen Datensatz ohne Tourdatei zurücklassen
            if os.path.exists(target_path):
                os.remove(target_path)
            delete_activity(conn, activity_id)
            raise

        os.remove(file_path)
        return activity_id
    finally:
        conn.close()
