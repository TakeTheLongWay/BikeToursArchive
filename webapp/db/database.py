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