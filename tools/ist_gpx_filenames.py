import os
import math
import shutil
import mysql.connector
import gpxpy
from datetime import timezone


# ===============================
# KONFIGURATION
# ===============================

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "hurtzming",
    "database": "tourbook",
}

BASE_PATH = r"C:\ProgramData\MySQL\MySQL Server 8.0\Uploads"
ARCHIVE_PATH = os.path.join(BASE_PATH, "activities")


# ===============================
# HILFSFUNKTIONEN
# ===============================

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def parse_gpx(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    track = gpx.tracks[0]
    segment = track.segments[0]

    name = track.name or "Unbenannte Tour"
    tour_type = track.type or "cycling"

    times = []
    coords = []
    distance_m = 0.0

    last_point = None

    for p in segment.points:
        coords.append((p.latitude, p.longitude, p.elevation, p.time))

        if p.time:
            times.append(p.time)

        if last_point:
            distance_m += haversine(
                last_point.latitude, last_point.longitude,
                p.latitude, p.longitude
            )
        last_point = p

    if not times:
        raise ValueError("Keine Zeitinformationen in GPX")

    start_time = min(times).astimezone(timezone.utc)
    end_time = max(times).astimezone(timezone.utc)

    duration_s = int((end_time - start_time).total_seconds())

    return {
        "name": name,
        "type": tour_type,
        "date": start_time.date(),
        "month": start_time.month,
        "year": start_time.year,
        "duration_s": duration_s,
        "distance_km": round(distance_m / 1000, 3),
        "coords": coords,
    }


# ===============================
# HAUPTLOGIK
# ===============================

def import_gpx_from_activities():
    print("\n=== Starte GPX-Import aus activities ===\n")

    if not os.path.exists(ARCHIVE_PATH):
        os.makedirs(ARCHIVE_PATH)

    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT activity_id, filename
        FROM activities
        WHERE filename IS NOT NULL
          AND LOWER(filename) LIKE '%.gpx'
    """)

    rows = cur.fetchall()
    print(f"Gefundene GPX-Dateien: {len(rows)}\n")

    for row in rows:
        filename = os.path.basename(row["filename"])
        source_file = os.path.join(BASE_PATH, filename)

        print(f"➡ Verarbeite: {source_file}")

        if not os.path.exists(source_file):
            print("   ❌ Datei nicht gefunden – übersprungen\n")
            continue

        try:
            tour = parse_gpx(source_file)

            target_file = os.path.join(ARCHIVE_PATH, filename)

            cur.execute("""
                INSERT INTO tours
                (name, date, duration_s, distance_km, type, month, year, file_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                tour["name"],
                tour["date"],
                tour["duration_s"],
                tour["distance_km"],
                tour["type"],
                tour["month"],
                tour["year"],
                target_file
            ))

            tour_id = cur.lastrowid

            for lat, lon, ele, time in tour["coords"]:
                cur.execute("""
                    INSERT INTO points
                    (tour_id, lat, lon, ele, time)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    tour_id,
                    lat,
                    lon,
                    ele,
                    time
                ))

            conn.commit()

            shutil.move(source_file, target_file)

            print(f"   ✅ Import OK → verschoben nach:")
            print(f"      {target_file}\n")

        except Exception as e:
            conn.rollback()
            print("   ❌ FEHLER – Import abgebrochen")
            print(f"      {e}\n")
            break

    cur.close()
    conn.close()

    print("=== GPX-Import abgeschlossen ===\n")


# ===============================
# START
# ===============================

if __name__ == "__main__":
    import_gpx_from_activities()
