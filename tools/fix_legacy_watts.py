"""Ø Leistung (avg_watts) und Kalorien (calories) der alten Strava-Touren korrigieren:
Beide Werte wurden mit Faktor 10 importiert.

Betroffen sind Touren ohne Gerät (device_name IS NULL, also nicht aus TCX-Dateien), deren Wert
ein Vielfaches von 10 ist. Die berechneten Kalorien (calories_calc) passt MySQL automatisch an.

Jede Korrektur darf nur einmal laufen; sie wird übersprungen, wenn die Werte schon plausibel sind
(keine Ø Leistung ab 1000 W bzw. im Schnitt unter 1500 kcal pro Stunde).

Aufruf aus dem Projektverzeichnis:
    .venv\\Scripts\\python -m tools.fix_legacy_watts [--dry-run]
"""
import argparse

from webapp.db.database import ensure_database, get_db_connection

# Ab diesem Wert gilt eine Ø Leistung als offensichtlich um Faktor 10 zu groß
IMPLAUSIBLE_AVG_WATTS = 1000
# Ab diesem Durchschnitt (kcal pro Stunde Gesamtdauer) gelten die Kalorien als um Faktor 10 zu groß
IMPLAUSIBLE_KCAL_PER_HOUR = 1500

LEGACY_WATTS_CONDITION = "device_name IS NULL AND avg_watts > 0 AND avg_watts % 10 = 0"
LEGACY_CALORIES_CONDITION = "device_name IS NULL AND calories > 0 AND calories % 10 = 0"


def fix_watts(cur, dry_run: bool) -> None:
    cur.execute(
        f"SELECT COUNT(*), MIN(avg_watts), MAX(avg_watts), SUM(avg_watts >= %s) FROM activities WHERE {LEGACY_WATTS_CONDITION}",
        (IMPLAUSIBLE_AVG_WATTS,),
    )
    count, min_watts, max_watts, implausible = cur.fetchone()

    if not implausible:
        print(f"Ø Leistung: keine Werte ab {IMPLAUSIBLE_AVG_WATTS} W – Korrektur wurde offenbar schon ausgeführt.")
        return

    print(f"Ø Leistung: {count} Touren mit {min_watts}–{max_watts} W, davon {implausible} ab {IMPLAUSIBLE_AVG_WATTS} W.")
    if dry_run:
        print(f"Würde avg_watts dieser {count} Touren durch 10 teilen.")
        return

    cur.execute(f"UPDATE activities SET avg_watts = ROUND(avg_watts / 10) WHERE {LEGACY_WATTS_CONDITION}")
    print(f"avg_watts für {cur.rowcount} Touren durch 10 geteilt.")


def fix_calories(cur, dry_run: bool) -> None:
    cur.execute(
        f"""
        SELECT COUNT(*), MIN(calories), MAX(calories), ROUND(AVG(calories * 3600 / NULLIF(elapsed_time_s, 0)))
        FROM activities WHERE {LEGACY_CALORIES_CONDITION}
        """
    )
    count, min_kcal, max_kcal, kcal_per_hour = cur.fetchone()

    if not kcal_per_hour or kcal_per_hour < IMPLAUSIBLE_KCAL_PER_HOUR:
        print(f"Kalorien: im Schnitt {kcal_per_hour} kcal/h – Korrektur wurde offenbar schon ausgeführt.")
        return

    print(f"Kalorien: {count} Touren mit {min_kcal}–{max_kcal} kcal, im Schnitt {kcal_per_hour} kcal/h.")
    if dry_run:
        print(f"Würde calories dieser {count} Touren durch 10 teilen.")
        return

    cur.execute(f"UPDATE activities SET calories = ROUND(calories / 10) WHERE {LEGACY_CALORIES_CONDITION}")
    print(f"calories für {cur.rowcount} Touren durch 10 geteilt.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="nur anzeigen, nichts speichern")
    args = parser.parse_args()

    # Legt die Spalte calories_calc an, falls die App noch nicht gestartet wurde
    ensure_database()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        fix_watts(cur, args.dry_run)
        fix_calories(cur, args.dry_run)
        if not args.dry_run:
            conn.commit()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
