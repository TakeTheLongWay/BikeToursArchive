from flask import Blueprint, current_app, jsonify, request

from ..db.database import mysql_connection_wrapper

appsettings_bp = Blueprint("appsettings", __name__)


def _row_to_dict(row):
    """Konvertiert einen DB-Row in ein serialisierbares Dict."""
    return {
        "id":            row["id"],
        "setting_key":   row["setting_key"],
        "setting_value": row["setting_value"] or "",
        "description":   row["description"] or "",
        "created_at":    str(row["created_at"]) if row["created_at"] else "",
        "updated_at":    str(row["updated_at"]) if row["updated_at"] else "",
    }


# ── GET alle Einstellungen ─────────────────────────────────────────────────────
@appsettings_bp.route("/api/appsettings", methods=["GET"])
@mysql_connection_wrapper
def api_appsettings_list(cursor):
    try:
        cursor.execute(
            "SELECT id, setting_key, setting_value, description, created_at, updated_at "
            "FROM appsettings ORDER BY setting_key ASC"
        )
        rows = cursor.fetchall() or []
        return jsonify([_row_to_dict(r) for r in rows])
    except Exception as exc:
        current_app.logger.error("FEHLER in api_appsettings_list: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ── POST neue Einstellung anlegen ─────────────────────────────────────────────
@appsettings_bp.route("/api/appsettings", methods=["POST"])
@mysql_connection_wrapper
def api_appsettings_create(cursor):
    try:
        data          = request.get_json(silent=True) or {}
        setting_key   = str(data.get("setting_key", "")).strip()
        setting_value = str(data.get("setting_value", "")).strip()
        description   = str(data.get("description", "")).strip()

        if not setting_key:
            return jsonify({"status": "error", "message": "Der Key darf nicht leer sein."}), 400

        if len(setting_key) > 100:
            return jsonify({"status": "error", "message": "Der Key ist zu lang (max. 100 Zeichen)."}), 400

        # Duplikat-Prüfung
        cursor.execute("SELECT id FROM appsettings WHERE setting_key = %s", (setting_key,))
        if cursor.fetchone():
            return jsonify({"status": "error", "message": f"Der Key '{setting_key}' existiert bereits."}), 409

        cursor.execute(
            "INSERT INTO appsettings (setting_key, setting_value, description) VALUES (%s, %s, %s)",
            (setting_key, setting_value or None, description or None),
        )
        new_id = cursor.lastrowid

        cursor.execute(
            "SELECT id, setting_key, setting_value, description, created_at, updated_at "
            "FROM appsettings WHERE id = %s",
            (new_id,),
        )
        row = cursor.fetchone()
        return jsonify({"status": "ok", **_row_to_dict(row)}), 201

    except Exception as exc:
        current_app.logger.error("FEHLER in api_appsettings_create: %s", exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


# ── PUT bestehende Einstellung aktualisieren ───────────────────────────────────
@appsettings_bp.route("/api/appsettings/<int:setting_id>", methods=["PUT"])
@mysql_connection_wrapper
def api_appsettings_update(cursor, setting_id):
    try:
        data          = request.get_json(silent=True) or {}
        setting_key   = str(data.get("setting_key", "")).strip()
        setting_value = str(data.get("setting_value", "")).strip()
        description   = str(data.get("description", "")).strip()

        if not setting_key:
            return jsonify({"status": "error", "message": "Der Key darf nicht leer sein."}), 400

        if len(setting_key) > 100:
            return jsonify({"status": "error", "message": "Der Key ist zu lang (max. 100 Zeichen)."}), 400

        # Existenz-Prüfung
        cursor.execute("SELECT id FROM appsettings WHERE id = %s", (setting_id,))
        if not cursor.fetchone():
            return jsonify({"status": "error", "message": "Einstellung nicht gefunden."}), 404

        # Duplikat-Prüfung (anderer Datensatz mit gleichem Key)
        cursor.execute(
            "SELECT id FROM appsettings WHERE setting_key = %s AND id != %s",
            (setting_key, setting_id),
        )
        if cursor.fetchone():
            return jsonify({"status": "error", "message": f"Der Key '{setting_key}' wird bereits verwendet."}), 409

        cursor.execute(
            "UPDATE appsettings SET setting_key = %s, setting_value = %s, description = %s WHERE id = %s",
            (setting_key, setting_value or None, description or None, setting_id),
        )

        cursor.execute(
            "SELECT id, setting_key, setting_value, description, created_at, updated_at "
            "FROM appsettings WHERE id = %s",
            (setting_id,),
        )
        row = cursor.fetchone()
        return jsonify({"status": "ok", **_row_to_dict(row)})

    except Exception as exc:
        current_app.logger.error("FEHLER in api_appsettings_update %s: %s", setting_id, exc)
        return jsonify({"status": "error", "message": str(exc)}), 500