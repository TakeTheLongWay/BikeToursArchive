from flask import Blueprint, jsonify, request

from ..db.database import mysql_connection_wrapper

goals_bp = Blueprint("goals", __name__)

GOAL_UI_TO_DB_KEY = {
    "annual": "goal_km_year",
    "monthly": "monthly",
    "weekly": "weekly",
    "daily": "daily",
}

VALID_GOAL_DB_KEYS = {"goal_km_year", "monthly", "weekly", "daily"}


@goals_bp.route("/api/goals", methods=["GET"])
@mysql_connection_wrapper
def api_get_goals(cursor):
    cursor.execute("SELECT key_name, value FROM goals")
    rows = cursor.fetchall() or []

    raw_goals = {row["key_name"]: round(float(row["value"] or 0), 2) for row in rows}
    goals = {
        "goal_km_year": raw_goals.get("goal_km_year", raw_goals.get("annual", 0.0)),
        "monthly": raw_goals.get("monthly", 0.0),
        "weekly": raw_goals.get("weekly", 0.0),
        "daily": raw_goals.get("daily", 0.0),
    }

    return jsonify({"status": "ok", "goals": goals})


@goals_bp.route("/api/goals", methods=["PUT"])
@mysql_connection_wrapper
def api_update_goal(cursor):
    data = request.get_json(silent=True) or {}
    key = data.get("key")
    value = data.get("value")

    if key is None:
        return jsonify({"status": "error", "message": "Key fehlt"}), 400

    db_key = GOAL_UI_TO_DB_KEY.get(key, key)
    if db_key not in VALID_GOAL_DB_KEYS:
        return jsonify({"status": "error", "message": f"Ungültiger Key: {key}"}), 400

    try:
        value_float = float(value)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": f"Ungültiger Wert: {value}"}), 400

    try:
        cursor.execute(
            "INSERT INTO goals (key_name, value) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE value = %s",
            (db_key, value_float, value_float),
        )

        if db_key == "goal_km_year":
            cursor.execute(
                "SELECT COUNT(*) AS cnt FROM goals WHERE key_name = %s",
                ("annual",),
            )
            row = cursor.fetchone() or {}
            if row.get("cnt", 0) > 0:
                cursor.execute(
                    "UPDATE goals SET value = %s WHERE key_name = %s",
                    (value_float, "annual"),
                )

        return jsonify({"status": "ok", "key": db_key, "value": value_float})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400