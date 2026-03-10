import csv
import mysql.connector
from mysql.connector import Error
import sys

# ------------------------------------------------------------
# KONFIGURATION
# ------------------------------------------------------------

CSV_FILE = r"C:\ProgramData\MySQL\MySQL Server 8.0\Uploads\activities_new.csv"

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "hurtzming",
    "database": "tourbook",
    "port": 3306,
    "autocommit": False
}

DELIMITER = ";"

# ------------------------------------------------------------
# SQL STATEMENTS
# ------------------------------------------------------------

INSERT_SQL = """
INSERT INTO activities (
    activity_id,
    activity_date,
    activity_name,
    activity_type,
    elapsed_time_s,
    distance_km,
    gear_name,
    filename,
    elevation_gain_m,
    min_elevation_m,
    max_elevation_m,
    avg_watts,
    calories,
    is_commute,
    bike_id,
    media
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s
)
"""

DELETE_ALL_SQL = "DELETE FROM activities"

# ------------------------------------------------------------
# HAUPTLOGIK
# ------------------------------------------------------------

def main():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✅ Verbindung zur MySQL-Datenbank hergestellt")
    except Error as e:
        print(f"❌ Datenbankverbindung fehlgeschlagen: {e}")
        sys.exit(1)

    inserted = 0

    try:
        with open(CSV_FILE, "r", encoding="utf-8", newline="") as csvfile:
            reader = csv.reader(csvfile, delimiter=DELIMITER)

            for line_no, row in enumerate(reader, start=1):
                print("\n----------------------------------------")
                print(f"CSV-Zeile {line_no}:")
                print(row)

                try:
                    cursor.execute(INSERT_SQL, row)

                    print("SQL-Insert:")
                    print(cursor.statement)

                    conn.commit()
                    inserted += 1
                    print("STATUS: OK")

                except Error as e:
                    print("STATUS: NOK")
                    print(f"❌ Insert-Fehler: {e}")

                    print("⚠️ Lösche alle Datensätze aus activities …")
                    cursor.execute(DELETE_ALL_SQL)
                    conn.commit()

                    print("🛑 Batchlauf abgebrochen")
                    sys.exit(1)

    except FileNotFoundError:
        print(f"❌ CSV-Datei nicht gefunden: {CSV_FILE}")
        sys.exit(1)

    finally:
        cursor.close()
        conn.close()

    print("\n==============================")
    print("✅ Batch-Insert abgeschlossen")
    print(f"Eingefügte Datensätze: {inserted}")
    print("==============================\n")


# ------------------------------------------------------------
# STARTPUNKT
# ------------------------------------------------------------

if __name__ == "__main__":
    main()
