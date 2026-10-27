import os
import shutil
from datetime import timedelta
from decimal import Decimal

from flask import current_app, has_app_context

from ..config import GPX_BASE_PATH, GPX_IMPORT_TARGET_DIR
from ..db.database import get_db_connection
from ..utils import build_gpx_path
from .track_files import parse_track_file, track_extension

# Toleranz für den Streckenvergleich bei der Duplikatprüfung
DUPLICATE_DISTANCE_TOLERANCE_KM = 0.01

# Abgleich TCX ↔ vorhandene Tour (z. B. Bosch-Aufzeichnung zur BikeTracker-GPX derselben Fahrt):
# Anteil der zeitlichen Überschneidung, bezogen auf die kürzere der beiden Fahrten
MATCH_MIN_TIME_OVERLAP = 0.5
# Erlaubte Abweichung der Distanz (relativ), damit Start/Stopp-Unterschiede der Geräte passen
MATCH_MAX_DISTANCE_DEVIATION = 0.25

# Spalten, die beim Abgleich ergänzt werden, wenn sie in der vorhandenen Tour fehlen (NULL, 0, leer).
# Name, Typ und Bike der vorhandenen Tour bleiben immer unverändert.
MERGE_COLUMNS = (
    "elapsed_time_s",
    "distance_km",
    "elevation_gain_m",
    "min_elevation_m",
    "max_elevation_m",
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

# Beim Ersetzen zusätzlich die Startzeit aus der TCX übernehmen
REPLACE_COLUMNS = ("activity_date",) + MERGE_COLUMNS

# "merge" = nur fehlende Werte ergänzen, "replace" = vorhandene Werte durch die TCX ersetzen
MERGE_MODES = ("merge", "replace")


class DuplicateActivityError(ValueError):
    """Die Tour ist bereits vorhanden (gleiche Startzeit und Strecke)."""

    def __init__(self, activity_id: int, activity_name: str):
        self.activity_id = activity_id
        self.activity_name = activity_name
        super().__init__(f"Tour bereits vorhanden: '{activity_name}' (ID {activity_id})")


class MatchDecisionRequired(Exception):
    """Zur Datei gibt es schon eine Tour; der Benutzer muss zwischen Ergänzen und Ersetzen wählen."""

    def __init__(self, activity: dict):
        self.activity = activity
        super().__init__(f"Tour bereits vorhanden: '{activity['activity_name']}' (ID {activity['activity_id']})")


def _get_target_dir():
    if has_app_context():
        return current_app.config.get("GPX_IMPORT_TARGET_DIR", GPX_IMPORT_TARGET_DIR)
    return GPX_IMPORT_TARGET_DIR


def _get_base_path():
    if has_app_context():
        return current_app.config.get("GPX_BASE_PATH", GPX_BASE_PATH)
    return GPX_BASE_PATH


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


def _is_missing(value) -> bool:
    return value is None or value == 0 or (isinstance(value, str) and not value.strip())


def find_matching_activity(conn, data: dict):
    """Sucht die Tour, die sich zeitlich am stärksten mit data überschneidet (oder None)."""
    start = data["activity_date"]
    duration_s = data.get("elapsed_time_s") or 0
    end = start + timedelta(seconds=duration_s)

    cur = conn.cursor(dictionary=True)
    try:
        # Kandidaten: Touren, deren Zeitraum [Start, Start + Dauer] den neuen Zeitraum berührt
        cur.execute(
            f"""
            SELECT activity_id, activity_name, activity_date, filename, {", ".join(MERGE_COLUMNS)}
            FROM activities
            WHERE activity_date <= %s
              AND DATE_ADD(activity_date, INTERVAL COALESCE(elapsed_time_s, 0) SECOND) >= %s
            """,
            (end, start),
        )
        candidates = cur.fetchall()
    finally:
        cur.close()

    best, best_overlap = None, 0.0
    for row in candidates:
        row_start = row["activity_date"]
        row_duration_s = row["elapsed_time_s"] or 0
        row_end = row_start + timedelta(seconds=row_duration_s)

        overlap_s = (min(end, row_end) - max(start, row_start)).total_seconds()
        shorter_s = min(duration_s, row_duration_s)
        if shorter_s <= 0 or overlap_s / shorter_s < MATCH_MIN_TIME_OVERLAP:
            continue

        if data.get("distance_km") and row["distance_km"]:
            deviation = abs(float(row["distance_km"]) - data["distance_km"]) / float(row["distance_km"])
            if deviation > MATCH_MAX_DISTANCE_DEVIATION:
                continue

        if overlap_s > best_overlap:
            best, best_overlap = row, overlap_s

    return best


def _update_activity(conn, activity_id: int, updates: dict) -> None:
    cur = conn.cursor()
    try:
        assignments = ", ".join(f"{column} = %s" for column in updates)
        cur.execute(
            f"UPDATE activities SET {assignments} WHERE activity_id = %s",
            (*updates.values(), activity_id),
        )
        conn.commit()
    finally:
        cur.close()


def _same_value(old, new) -> bool:
    if isinstance(old, (int, float, Decimal)) and isinstance(new, (int, float)):
        return abs(float(old) - float(new)) < 1e-6
    return old == new


def _merge_into_activity(conn, activity: dict, data: dict, replace: bool) -> list:
    """
    Übernimmt TCX-Werte in die vorhandene Tour; liefert die Namen der geänderten Spalten.
    replace=False: nur fehlende Felder ergänzen. replace=True: alle Werte (inkl. Startzeit) durch
    die TCX-Werte ersetzen; Felder, für die die TCX keinen Wert hat, bleiben erhalten.
    """
    columns = REPLACE_COLUMNS if replace else MERGE_COLUMNS
    updates = {
        column: data[column]
        for column in columns
        if not _is_missing(data.get(column))
        and (_is_missing(activity.get(column)) or (replace and not _same_value(activity.get(column), data[column])))
    }
    if updates:
        _update_activity(conn, activity["activity_id"], updates)
    return list(updates)


def _store_track_file(conn, activity_id: int, file_path: str, filename: str) -> None:
    extension = track_extension(filename or file_path)
    target_dir = _get_target_dir()
    os.makedirs(target_dir, exist_ok=True)
    shutil.copy2(file_path, os.path.join(target_dir, f"{activity_id}{extension}"))
    update_filename(conn, activity_id, f"activities/{activity_id}{extension}")


def merge_or_import_track_file(file_path: str, filename: str = None, mode: str = None) -> dict:
    """
    Gibt es zur Datei bereits eine Tour (zeitliche Überschneidung, ähnliche Distanz), entscheidet mode:
    - "merge":   nur fehlende Werte ergänzen
    - "replace": vorhandene Werte und Tourdatei durch die der TCX ersetzen
    - None:      nichts ändern, MatchDecisionRequired auslösen (Rückfrage beim Benutzer)
    Ohne passende Tour wird die Datei normal importiert.

    Ergebnis: {"activity_id", "activity_name", "merged": bool, "mode", "updated_fields": [...]}.
    Ist die Tour vorhanden und ändert sich nichts, folgt DuplicateActivityError.
    """
    if mode not in (None, *MERGE_MODES):
        raise ValueError(f"Unbekannter Abgleich-Modus: {mode}")

    track_data = parse_track_file(file_path, filename)

    conn = get_db_connection()
    try:
        activity = find_matching_activity(conn, track_data)
        if activity is None:
            conn.close()
            conn = None
            activity_id = process_track_file(file_path, filename)
            return {
                "activity_id": activity_id,
                "activity_name": track_data["activity_name"],
                "merged": False,
                "mode": None,
                "updated_fields": [],
            }

        if mode is None:
            raise MatchDecisionRequired(activity)

        activity_id = int(activity["activity_id"])
        replace = mode == "replace"
        updated_fields = _merge_into_activity(conn, activity, track_data, replace)

        # Beim Ersetzen wird die TCX zur Tourdatei (Karte/Profil aus der TCX); beim Ergänzen nur,
        # wenn die Tour noch keine (vorhandene) Tourdatei hat.
        new_filename = f"activities/{activity_id}{track_extension(filename or file_path)}"
        current_file = activity.get("filename")
        current_path = build_gpx_path(_get_base_path(), current_file) if current_file else ""
        file_missing = not current_file or not os.path.exists(current_path)
        if file_missing or (replace and current_file != new_filename):
            _store_track_file(conn, activity_id, file_path, filename)
            updated_fields.append("filename")

            # Ersetzte alte Tourdatei (z. B. BikeTracker-GPX) erst löschen, wenn die TCX gespeichert ist
            if replace and not file_missing:
                try:
                    os.remove(current_path)
                except OSError as exc:
                    if has_app_context():
                        current_app.logger.warning("Alte Tourdatei %s nicht gelöscht: %s", current_path, exc)

        if not updated_fields:
            raise DuplicateActivityError(activity_id, activity["activity_name"])

        os.remove(file_path)
        return {
            "activity_id": activity_id,
            "activity_name": activity["activity_name"],
            "merged": True,
            "mode": mode,
            "updated_fields": updated_fields,
        }
    finally:
        if conn is not None:
            conn.close()


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
