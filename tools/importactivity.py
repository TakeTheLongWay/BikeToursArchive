import csv
import os
import sys
from datetime import datetime

# ------------------------------------------------------------
# KONFIGURATION
# ------------------------------------------------------------

INPUT_FILE = r"C:\ProgramData\MySQL\MySQL Server 8.0\Uploads\activities_edit.csv"
OUTPUT_FILE = r"C:\ProgramData\MySQL\MySQL Server 8.0\Uploads\activities_new.csv"

DELIMITER = ";"
EXPECTED_COLUMNS = 16  # exakt gemäß CREATE TABLE

# ------------------------------------------------------------
# HILFSFUNKTIONEN
# ------------------------------------------------------------

def clean_string(value: str) -> str:
    """Entfernt BOM, Whitespace und unsichtbare Zeichen"""
    if value is None:
        return ""
    return value.replace("\ufeff", "").strip()


def parse_int(value: str) -> int:
    value = clean_string(value)
    if value == "":
        return 0
    try:
        return int(float(value))
    except ValueError:
        return 0


def parse_decimal(value: str, scale: int = 3) -> float:
    value = clean_string(value).replace(",", ".")
    if value == "":
        return 0.0
    try:
        return round(float(value), scale)
    except ValueError:
        return 0.0


def parse_datetime(value: str) -> str:
    value = clean_string(value)
    if value == "":
        return "1970-01-01 00:00:00"
    try:
        dt = datetime.strptime(value, "%d.%m.%Y %H:%M")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return "1970-01-01 00:00:00"


# ------------------------------------------------------------
# HAUPTLOGIK
# ------------------------------------------------------------

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Eingabedatei nicht gefunden: {INPUT_FILE}")
        sys.exit(1)

    processed = 0
    rejected = 0

    with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as infile, \
         open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as outfile:

        reader = csv.reader(infile, delimiter=DELIMITER)
        writer = csv.writer(outfile, delimiter=DELIMITER, lineterminator="\r\n")

        for line_no, row in enumerate(reader, start=1):
            print(f"▶ Zeile {line_no}: {row}")

            # Spaltenanzahl prüfen
            if len(row) != EXPECTED_COLUMNS:
                print(f"  ⚠️ Verworfen (Spaltenanzahl {len(row)} != {EXPECTED_COLUMNS})")
                rejected += 1
                continue

            try:
                cleaned_row = [
                    parse_int(row[0]),                     # activity_id
                    parse_datetime(row[1]),               # activity_date
                    clean_string(row[2]) or "UNBEKANNT",  # activity_name
                    clean_string(row[3]) or "unknown",    # activity_type
                    parse_int(row[4]),                     # elapsed_time_s
                    parse_decimal(row[5], 3),              # distance_km
                    clean_string(row[6]),                  # gear_name
                    clean_string(row[7]),                  # filename
                    parse_decimal(row[8], 1),              # elevation_gain_m
                    parse_decimal(row[9], 1),              # min_elevation_m
                    parse_decimal(row[10], 1),             # max_elevation_m
                    parse_int(row[11]),                    # avg_watts
                    parse_int(row[12]),                    # calories
                    1 if clean_string(row[13]) not in ("", "0") else 0,  # is_commute
                    parse_int(row[14]),                    # bike_id
                    clean_string(row[15])                  # media
                ]

                writer.writerow(cleaned_row)
                processed += 1
                print(f"  ✅ Übernommen")

            except Exception as e:
                print(f"  ❌ Verworfen (Fehler: {e})")
                rejected += 1

    print("\n==============================")
    print("✅ Import abgeschlossen")
    print(f"Übernommene Zeilen : {processed}")
    print(f"Verworfene Zeilen  : {rejected}")
    print(f"Zieldatei          : {OUTPUT_FILE}")
    print("==============================\n")


# ------------------------------------------------------------
# STARTPUNKT
# ------------------------------------------------------------

if __name__ == "__main__":
    main()
