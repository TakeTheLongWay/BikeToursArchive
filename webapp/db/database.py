from functools import wraps

import mysql.connector
from flask import jsonify

from ..config import DB_CONFIG


def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def _ensure_tour_names_table(cursor):
    cursor.execute("SHOW TABLES LIKE 'tour_names'")
    if cursor.fetchone():
        return

    cursor.execute(
        """
        CREATE TABLE `tour_names` (
          `id` bigint NOT NULL AUTO_INCREMENT,
          `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
          `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`),
          UNIQUE KEY `uq_tour_names_name` (`name`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )

    # Einmalig mit den vorhandenen Tournamen befüllen, ohne automatisch
    # erzeugte Namen aus dem GPX-Import ("Tour 2026-10-17T07:20:17Z")
    cursor.execute(
        """
        INSERT IGNORE INTO tour_names (name)
        SELECT DISTINCT TRIM(activity_name)
        FROM activities
        WHERE TRIM(activity_name) <> ''
          AND activity_name NOT REGEXP '^Tour [0-9]{4}-[0-9]{2}-[0-9]{2}T'
        """
    )
    print(f"Tabelle tour_names angelegt ({cursor.rowcount} Tournamen übernommen).")


def _ensure_biketracker_imports_table(cursor):
    cursor.execute("SHOW TABLES LIKE 'biketracker_imports'")
    if cursor.fetchone():
        return

    # Merkt sich, welche BikeTracker-Datei (Drive-ID bzw. Dateiname) zu welcher Tour gehört;
    # siehe Create_Table_BiketrackerImports.sql
    cursor.execute(
        """
        CREATE TABLE `biketracker_imports` (
          `file_id` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
          `filename` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
          `activity_id` bigint NOT NULL,
          `imported_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (`file_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    print("Tabelle biketracker_imports angelegt.")


def _ensure_media_table(cursor):
    cursor.execute("SHOW TABLES LIKE 'media'")
    if cursor.fetchone():
        return

    # Bilder/Videos aus dem Strava-Export mit Bildunterschrift; siehe Create_Table_Media.sql
    cursor.execute(
        """
        CREATE TABLE `media` (
          `filename` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
          `caption` text COLLATE utf8mb4_unicode_ci,
          `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (`filename`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    print("Tabelle media angelegt.")


def _ensure_temperature_columns(cursor):
    # Min./Max.-Temperatur aus den GPX-Extensions (bt:tempMin / bt:tempMax)
    for column in ("temp_min_c", "temp_max_c"):
        cursor.execute("SHOW COLUMNS FROM activities LIKE %s", (column,))
        if cursor.fetchone():
            continue
        cursor.execute(f"ALTER TABLE activities ADD COLUMN `{column}` decimal(4,1) DEFAULT NULL")
        print(f"Spalte activities.{column} angelegt.")


# Zusatzfelder aus TCX-Dateien (Lap-Summen bzw. aus den Trackpoints berechnet)
TCX_COLUMNS = (
    # Lap/TotalTimeSeconds: reine Fahrzeit ohne Pausen
    ("moving_time_s", "int"),
    # Lap/MaximumSpeed (m/s, umgerechnet in km/h)
    ("max_speed_kmh", "decimal(5,1)"),
    # Lap/Cadence bzw. Maximum aus Trackpoint/Cadence
    ("avg_cadence_rpm", "smallint"),
    ("max_cadence_rpm", "smallint"),
    # Maximum aus Trackpoint/Extensions/TPX/Watts
    ("max_watts", "int"),
    # Lap/AverageHeartRateBpm / MaximumHeartRateBpm (0 = kein Sensor -> NULL)
    ("avg_heart_rate_bpm", "smallint"),
    ("max_heart_rate_bpm", "smallint"),
    # Activity/Creator/Name, z. B. "Bosch eBike Connect with barometer"
    ("device_name", "varchar(255) COLLATE utf8mb4_unicode_ci"),
)


def _ensure_tcx_columns(cursor):
    for column, column_type in TCX_COLUMNS:
        cursor.execute("SHOW COLUMNS FROM activities LIKE %s", (column,))
        if cursor.fetchone():
            continue
        cursor.execute(f"ALTER TABLE activities ADD COLUMN `{column}` {column_type} DEFAULT NULL")
        print(f"Spalte activities.{column} angelegt.")


def _ensure_calories_calc_column(cursor):
    cursor.execute("SHOW COLUMNS FROM activities LIKE 'calories_calc'")
    if cursor.fetchone():
        return

    # Kalorien aus Ø Leistung und Fahrzeit (ohne Fahrzeit: Gesamtdauer): kcal = Watt * Sekunden / 1000.
    # Als STORED-Spalte berechnet MySQL den Wert für alle bestehenden Touren und bei jedem
    # INSERT/UPDATE neu; ohne Leistungs- oder Zeitwert bleibt er NULL.
    cursor.execute(
        """
        ALTER TABLE activities ADD COLUMN `calories_calc` int
        GENERATED ALWAYS AS (
          ROUND(NULLIF(avg_watts, 0) * COALESCE(NULLIF(moving_time_s, 0), NULLIF(elapsed_time_s, 0)) / 1000)
        ) STORED
        """
    )
    print("Spalte activities.calories_calc angelegt.")


def _ensure_tour_plans_table(cursor):
    cursor.execute("SHOW TABLES LIKE 'tour_plans'")
    if cursor.fetchone():
        return

    # Planungssessions der Tourplanung: draft ist der laufend gesicherte Arbeitsstand,
    # saved_data der zuletzt per "Speichern" festgeschriebene Stand
    cursor.execute(
        """
        CREATE TABLE `tour_plans` (
          `id` int NOT NULL AUTO_INCREMENT,
          `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
          `draft` json NOT NULL,
          `saved_data` json DEFAULT NULL,
          `saved_at` datetime DEFAULT NULL,
          `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
          `updated_at` datetime(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
          PRIMARY KEY (`id`),
          KEY `idx_tour_plans_updated` (`updated_at`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
    )
    print("Tabelle tour_plans angelegt.")


# Homebase (Mittelpunkt und Zoomstufe der Karte auf der Tourplanungsseite); Startwert München-Zentrum
HOMEBASE_SETTINGS = {
    "homebase.lat": ("48.137", "Breitengrad der Homebase (Kartenmitte Tourplanung)"),
    "homebase.lon": ("11.575", "Längengrad der Homebase (Kartenmitte Tourplanung)"),
    "homebase.zoom": ("10", "Zoomstufe der Karte auf der Tourplanungsseite"),
}

# Routing der Tourplanung über BRouter, ein Profil je Aktivität (PLANNING_ACTIVITIES);
# weitere Profile z. B. fastbike, safety, shortest, hiking-beta
PLANNING_SETTINGS = {
    "planning.routing_profile.bike": ("trekking", "BRouter-Profil der Tourplanung für Aktivität Fahrrad"),
    "planning.routing_profile.mtb": ("mtb", "BRouter-Profil der Tourplanung für Aktivität Mtb"),
    "planning.routing_profile.hiking": ("hiking-mountain", "BRouter-Profil der Tourplanung für Aktivität Wandern"),
}


def _ensure_planning_settings(cursor):
    # INSERT IGNORE: bestehende (ggf. geänderte) Werte bleiben unangetastet
    for key, (value, description) in {**HOMEBASE_SETTINGS, **PLANNING_SETTINGS}.items():
        cursor.execute(
            "INSERT IGNORE INTO appsettings (setting_key, setting_value, description) VALUES (%s, %s, %s)",
            (key, value, description),
        )
        if cursor.rowcount:
            print(f"Einstellung {key} angelegt.")


def _ensure_default_bike_trigger(cursor):
    cursor.execute(
        """
        SELECT 1 FROM information_schema.triggers
        WHERE trigger_schema = DATABASE() AND trigger_name = 'trg_activities_default_bike'
        """
    )
    if cursor.fetchone():
        return

    # Standard-Bike aus bikes.standard_bike (Name oder ID) für jede neue Tour ohne Bike,
    # unabhängig vom Importweg; siehe Create_Trigger_DefaultBike.sql
    cursor.execute(
        """
        CREATE TRIGGER `trg_activities_default_bike`
        BEFORE INSERT ON `activities`
        FOR EACH ROW
        BEGIN
          IF NEW.bike_id IS NULL OR NEW.bike_id = 0 THEN
            SET NEW.bike_id = (
              SELECT b.id
              FROM bikes b
              JOIN appsettings s ON s.setting_key = 'bikes.standard_bike'
              WHERE b.name = TRIM(s.setting_value)
                 OR CAST(b.id AS CHAR) COLLATE utf8mb4_unicode_ci = TRIM(s.setting_value)
              ORDER BY b.name = TRIM(s.setting_value) DESC
              LIMIT 1
            );
          END IF;
        END
        """
    )
    print("Trigger trg_activities_default_bike angelegt.")


def ensure_database():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)
        cursor.execute("SELECT 1")
        cursor.fetchall()
        print("Datenbankverbindung erfolgreich hergestellt.")

        _ensure_tour_names_table(cursor)
        _ensure_biketracker_imports_table(cursor)
        _ensure_media_table(cursor)
        _ensure_temperature_columns(cursor)
        _ensure_tcx_columns(cursor)
        _ensure_calories_calc_column(cursor)
        _ensure_default_bike_trigger(cursor)
        _ensure_planning_settings(cursor)
        _ensure_tour_plans_table(cursor)
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Datenbankfehler beim Start: {err}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def mysql_connection_wrapper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True, buffered=True)

            result = func(cursor, *args, **kwargs)

            if conn.in_transaction:
                conn.commit()

            return result
        except mysql.connector.Error as err:
            if conn and conn.in_transaction:
                conn.rollback()
            return jsonify({"error": str(err)}), 500
        except Exception:
            if conn and conn.in_transaction:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    return wrapper