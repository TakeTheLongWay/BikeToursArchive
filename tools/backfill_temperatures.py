"""Min./Max.-Temperatur (bt:tempMin / bt:tempMax) für bestehende Touren aus ihren GPX-Dateien nachtragen.

Aufruf aus dem Projektverzeichnis:
    .venv\\Scripts\\python -m tools.backfill_temperatures [--dry-run]
"""
import argparse
import os

import gpxpy

from webapp.config import GPX_BASE_PATH
from webapp.db.database import ensure_database, get_db_connection
from webapp.services.gpx_utils import _extension_float
from webapp.utils.common import build_gpx_path


def read_temperatures(gpx_path: str):
    with open(gpx_path, "r", encoding="utf-8") as file_handle:
        gpx = gpxpy.parse(file_handle)
    return _extension_float(gpx, "tempMin"), _extension_float(gpx, "tempMax")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="nur anzeigen, nichts speichern")
    args = parser.parse_args()

    # Legt die Spalten temp_min_c / temp_max_c an, falls die App noch nicht gestartet wurde
    ensure_database()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT activity_id, filename
            FROM activities
            WHERE filename IS NOT NULL
              AND temp_min_c IS NULL
              AND temp_max_c IS NULL
            """
        )
        rows = cur.fetchall()

        updated = without_values = missing = failed = 0
        for activity_id, filename in rows:
            gpx_path = build_gpx_path(GPX_BASE_PATH, filename)
            if not os.path.exists(gpx_path):
                missing += 1
                continue

            try:
                temp_min, temp_max = read_temperatures(gpx_path)
            except Exception as err:
                failed += 1
                print(f"Fehler bei Tour {activity_id} ({filename}): {err}")
                continue

            if temp_min is None and temp_max is None:
                without_values += 1
                continue

            print(f"Tour {activity_id}: Min {temp_min} °C, Max {temp_max} °C")
            if not args.dry_run:
                cur.execute(
                    "UPDATE activities SET temp_min_c = %s, temp_max_c = %s WHERE activity_id = %s",
                    (temp_min, temp_max, activity_id),
                )
            updated += 1

        if not args.dry_run:
            conn.commit()

        print(
            f"\n{len(rows)} Touren geprüft: {updated} {'würden befüllt' if args.dry_run else 'befüllt'}, "
            f"{without_values} ohne Temperaturwerte, {missing} ohne GPX-Datei, {failed} fehlerhaft."
        )
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
