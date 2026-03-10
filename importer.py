import os
import math
import shutil
from datetime import timezone

import gpxpy

from database import get_db_connection

# Zielverzeichnis für finale GPX-Dateien (wie im bestehenden Stand)
TARGET_DIR = r"C:\ProgramData\MySQL\MySQL Server 8.0\Uploads\activities"
os.makedirs(TARGET_DIR, exist_ok=True)


# ======================================================
# HILFSFUNKTIONEN
# ======================================================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Meter
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def parse_gpx(file_path: str) -> dict:
    """
    Liest eine GPX-Datei und extrahiert Tourdaten
    """
    with open(file_path, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    if not gpx.tracks:
        raise ValueError("GPX enthält keine Tracks")

    track = gpx.tracks[0]
    segment = track.segments[0]

    name = track.name or "Unbenannte Tour"
    activity_type = track.type or "cycling"

    distance_m = 0.0
    elevation_gain = 0.0
    times = []

    last_point = None
    for p in segment.points:
        if p.time:
            times.append(p.time)

        if last_point is not None:
            distance_m += haversine(
                last_point.latitude,
                last_point.longitude,
                p.latitude,
                p.longitude,
            )

            if p.elevation is not None and last_point.elevation is not None:
                diff = p.elevation - last_point.elevation
                if diff > 0:
                    elevation_gain += diff

        last_point = p

    if not times:
        raise ValueError("GPX enthält keine Zeitinformationen")

    start_time = min(times).astimezone(timezone.utc)
    end_time = max(times).astimezone(timezone.utc)
    duration_s = int((end_time - start_time).total_seconds())

    # MySQL DATETIME ist i.d.R. naive -> tzinfo entfernen (UTC)
    start_time_naive = start_time.replace(tzinfo=None)

    return {
        "activity_date": start_time_naive,
        "activity_name": name,
        "activity_type": activity_type,
        "elapsed_time_s": duration_s,
        "distance_km": round(distance_m / 1000, 3),
        "elevation_gain_m": round(elevation_gain, 1),
    }


# ======================================================
# DATENBANKLOGIK
# ======================================================

def insert_activity(conn, data: dict) -> int:
    """
    Legt einen Datensatz in activities an und gibt activity_id zurück
    """
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
    cur.close()
    return int(activity_id)


def update_filename(conn, activity_id: int, filename: str):
    cur = conn.cursor()
    cur.execute(
        "UPDATE activities SET filename = %s WHERE activity_id = %s",
        (filename, activity_id),
    )
    conn.commit()
    cur.close()


# ======================================================
# ÖFFENTLICHE API – WIRD VON app.py VERWENDET
# ======================================================

def process_gpx_file(gpx_path: str) -> int:
    """
    Importiert eine GPX-Datei:
    - liest GPX
    - legt Datensatz in activities an
    - benennt Datei nach activity_id um
    - verschiebt Datei ins activities-Verzeichnis
    - setzt filename (relativ) in DB

    Rückgabewert:
        activity_id (int)
    """
    print(f"Starte GPX-Import: {gpx_path}")

    # GPX lesen
    gpx_data = parse_gpx(gpx_path)

    conn = get_db_connection()
    try:
        # 1) Insert activities
        activity_id = insert_activity(conn, gpx_data)

        # 2) Datei nach activity_id umbenennen und ins Ziel verschieben
        new_filename = f"activities/{activity_id}.gpx"
        target_path = os.path.join(TARGET_DIR, f"{activity_id}.gpx")

        os.makedirs(TARGET_DIR, exist_ok=True)

        # copy + remove (robust, auch wenn Quelle auf anderem Volume liegt)
        shutil.copy2(gpx_path, target_path)
        os.remove(gpx_path)

        print(f"Datei verschoben nach: {target_path}")

        # 3) Filename in DB setzen
        update_filename(conn, activity_id, new_filename)

        print("GPX-Import erfolgreich abgeschlossen\n")
        return activity_id

    finally:
        conn.close()
