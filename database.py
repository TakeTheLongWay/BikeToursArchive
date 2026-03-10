import mysql.connector
from functools import wraps
from flask import jsonify

DB_CONFIG = {
    'user': 'root',
    'password': 'hurtzming',
    'host': '127.0.0.1',
    'database': 'tourbook',
    'allow_local_infile': True
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def ensure_database():
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(buffered=True)
        cursor.execute("SELECT 1")
        cursor.fetchall() # Ergebnisse leeren
        print("Datenbankverbindung erfolgreich hergestellt.")
    except mysql.connector.Error as err:
        print(f"Datenbankfehler beim Start: {err}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def mysql_connection_wrapper(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True, buffered=True)
            return func(cursor, *args, **kwargs)
        except mysql.connector.Error as err:
            return jsonify({"error": str(err)}), 500
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    return wrapper