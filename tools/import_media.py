"""Bilder/Videos mit Bildunterschrift aus dem Strava-Export (legacy_data/media.csv) in die Tabelle media importieren.

Der Pfadanteil "media/" wird aus dem Medien-Dateinamen entfernt, gespeichert wird nur der Dateiname.
Bereits vorhandene Dateinamen werden aktualisiert, der Import kann also mehrfach laufen.

Aufruf aus dem Projektverzeichnis:
    .venv\\Scripts\\python -m tools.import_media [--csv PFAD] [--dry-run]
"""
import argparse
import csv
from pathlib import Path

from webapp.db.database import ensure_database, get_db_connection

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "legacy_data" / "media.csv"
MEDIA_PREFIX = "media/"


def strip_media_prefix(filename: str) -> str:
    filename = filename.strip()
    if filename.startswith(MEDIA_PREFIX):
        filename = filename[len(MEDIA_PREFIX):]
    return filename


def read_media_csv(csv_path: Path):
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as file_handle:
        for row in csv.DictReader(file_handle):
            filename = strip_media_prefix(row["Medien-Dateiname"])
            if not filename:
                continue
            caption = row["Medienunterschrift"].strip() or None
            yield filename, caption


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Pfad zur media.csv")
    parser.add_argument("--dry-run", action="store_true", help="nur anzeigen, nichts speichern")
    args = parser.parse_args()

    rows = list(read_media_csv(args.csv))
    with_caption = sum(1 for _, caption in rows if caption)

    if args.dry_run:
        for filename, caption in rows[:10]:
            print(f"{filename}: {caption}")
        print(f"\n{len(rows)} Einträge würden importiert ({with_caption} mit Bildunterschrift).")
        return

    # Legt die Tabelle media an, falls die App noch nicht gestartet wurde
    ensure_database()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.executemany(
            """
            INSERT INTO media (filename, caption)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE caption = VALUES(caption)
            """,
            rows,
        )
        conn.commit()
        print(f"{len(rows)} Einträge importiert ({with_caption} mit Bildunterschrift).")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
