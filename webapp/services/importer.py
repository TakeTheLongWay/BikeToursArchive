import os
import shutil

from flask import current_app, has_app_context

from ..config import GPX_IMPORT_TARGET_DIR
from ..db.database import get_db_connection
from .gpx_utils import parse_gpx


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


def process_gpx_file(gpx_path: str) -> int:
    gpx_data = parse_gpx(gpx_path)
    target_dir = _get_target_dir()
    os.makedirs(target_dir, exist_ok=True)

    conn = get_db_connection()
    try:
        activity_id = insert_activity(conn, gpx_data)

        new_filename = f"activities/{activity_id}.gpx"
        target_path = os.path.join(target_dir, f"{activity_id}.gpx")

        shutil.copy2(gpx_path, target_path)
        os.remove(gpx_path)

        update_filename(conn, activity_id, new_filename)

        return activity_id
    finally:
        conn.close()


def insert_strava_activity(strava_data: dict) -> int:
    """
    Speichert eine Strava-Aktivitaet direkt in die activities-Tabelle.
    Wirft ValueError bei Duplikat (strava_id bereits vorhanden).
    """
    dist_m = strava_data.get("distance", 0) or 0
    dist_km = round(dist_m / 1000, 2)
    elevation_m = strava_data.get("total_elevation_gain", 0) or 0
    start_date = (strava_data.get("start_date_local") or "")[:10]
    sport_type = strava_data.get("sport_type") or strava_data.get("type") or "Ride"

    conn = get_db_connection()
    try:
        cur = conn.cursor()

        # Duplikat-Pruefung ueber strava_id
        cur.execute(
            "SELECT activity_id FROM activities WHERE strava_id = %s",
            (strava_data["id"],)
        )
        if cur.fetchone():
            raise ValueError(f"Aktivitaet {strava_data['id']} ist bereits importiert.")

        cur.execute(
            """
            INSERT INTO activities (
                activity_date,
                activity_name,
                activity_type,
                elapsed_time_s,
                distance_km,
                elevation_gain_m,
                filename,
                strava_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                start_date,
                strava_data.get("name", "Strava-Aktivitaet"),
                sport_type,
                strava_data.get("elapsed_time", 0),
                dist_km,
                round(elevation_m, 1),
                None,
                strava_data["id"],
            ),
        )
        activity_id = cur.lastrowid
        conn.commit()
        cur.close()
        return int(activity_id)
    finally:
        conn.close()

def _build_gpx_from_streams(activity_data: dict, streams) -> str:
    """Erstellt einen GPX-String aus Strava-Streams (latlng + altitude).
    streams kann ein Dict sein (key_by_type=true) oder eine Liste (key_by_type=false).
    """
    latlng_data = []
    altitude_data = []

    if isinstance(streams, dict):
        # key_by_type=true: {"latlng": {"data": [...]}, "altitude": {"data": [...]}}
        latlng_data = streams.get("latlng", {}).get("data", [])
        altitude_data = streams.get("altitude", {}).get("data", [])
    else:
        # key_by_type=false: [{"type": "latlng", "data": [...]}, ...]
        for stream in streams:
            if isinstance(stream, dict):
                if stream.get("type") == "latlng":
                    latlng_data = stream.get("data", [])
                elif stream.get("type") == "altitude":
                    altitude_data = stream.get("data", [])

    name = activity_data.get("name", "Strava-Aktivität").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    start_date = activity_data.get("start_date", "")

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<gpx version="1.1" creator="MyBikeLog" xmlns="http://www.topografix.com/GPX/1/1">',
        f'  <metadata><name>{name}</name></metadata>',
        '  <trk>',
        f'    <name>{name}</name>',
        '    <trkseg>',
    ]

    for i, (lat, lon) in enumerate(latlng_data):
        ele = altitude_data[i] if i < len(altitude_data) else 0
        lines.append(f'      <trkpt lat="{lat}" lon="{lon}"><ele>{ele:.1f}</ele></trkpt>')

    lines += ['    </trkseg>', '  </trk>', '</gpx>']
    return "\n".join(lines)


def save_strava_gpx(activity_id: int, activity_data: dict, streams: list) -> None:
    """
    Erstellt eine GPX-Datei aus Strava-Streams und speichert sie lokal.
    Aktualisiert anschließend den filename-Eintrag in der DB.
    """
    if not streams:
        return

    target_dir = _get_target_dir()
    os.makedirs(target_dir, exist_ok=True)

    gpx_content = _build_gpx_from_streams(activity_data, streams)
    target_path = os.path.join(target_dir, f"{activity_id}.gpx")

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(gpx_content)

    conn = get_db_connection()
    try:
        update_filename(conn, activity_id, f"activities/{activity_id}.gpx")
    finally:
        conn.close()