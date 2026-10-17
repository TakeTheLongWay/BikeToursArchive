import os
import shutil

from flask import current_app, has_app_context

from ..config import GPX_IMPORT_TARGET_DIR
from ..db.database import get_db_connection
from .gpx_utils import parse_gpx

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


def insert_activity(conn, data: dict) -> int:
    sql = """
        INSERT INTO activities (
            activity_date,
            activity_name,
            activity_type,
            elapsed_time_s,
            distance_km,
            elevation_gain_m,
            filename
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """

    cur = conn.cursor()
    try:
        cur.execute(
            sql,
            (
                data["activity_date"],
                data["activity_name"],
                data["activity_type"],
                data["elapsed_time_s"],
                data["distance_km"],
                data["elevation_gain_m"],
                None,
            ),
        )
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


def process_gpx_file(gpx_path: str) -> int:
    gpx_data = parse_gpx(gpx_path)
    target_dir = _get_target_dir()
    os.makedirs(target_dir, exist_ok=True)

    conn = get_db_connection()
    try:
        duplicate = find_duplicate(conn, gpx_data)
        if duplicate:
            raise DuplicateActivityError(int(duplicate[0]), duplicate[1])

        activity_id = insert_activity(conn, gpx_data)

        new_filename = f"activities/{activity_id}.gpx"
        target_path = os.path.join(target_dir, f"{activity_id}.gpx")

        shutil.copy2(gpx_path, target_path)
        os.remove(gpx_path)

        update_filename(conn, activity_id, new_filename)

        return activity_id
    finally:
        conn.close()

