import logging
import os
from datetime import datetime, date, timedelta

import gpxpy
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from database import ensure_database, mysql_connection_wrapper
from importer import process_gpx_file

app = Flask(__name__, static_folder="static", template_folder="templates")

GPX_BASE_PATH = r"C:\ProgramData\MySQL\MySQL Server 8.0\Uploads"
UPLOAD_TMP_DIR = os.path.join(os.path.dirname(__file__), "uploads_tmp")
os.makedirs(UPLOAD_TMP_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app.logger.setLevel(logging.INFO)

ensure_database()

GOAL_UI_TO_DB_KEY = {
    "annual": "goal_km_year",
    "monthly": "monthly",
    "weekly": "weekly",
    "daily": "daily",
}


def get_db_type(filter_type):
    """Übersetzt Dashboard-Filter in DB-Typen (activity_type)."""
    if filter_type == "Alle" or not filter_type:
        return None
    if filter_type == "per pedes":
        return "hiking"
    return filter_type


@app.route("/")
def index():
    now = datetime.now()
    return render_template("index.html", current_year=now.year, current_month=now.month)


@app.route("/mygoals")
def mygoals():
    return render_template("mygoals.html")


@app.route("/api/goals", methods=["GET"])
@mysql_connection_wrapper
def api_get_goals(cursor):
    cursor.execute("SELECT key_name, value FROM goals")
    rows = cursor.fetchall() or []
    goals = {r["key_name"]: round(float(r["value"] or 0), 2) for r in rows}
    return jsonify({"status": "ok", "goals": goals})


@app.route("/api/goals", methods=["PUT"])
@mysql_connection_wrapper
def api_update_goal(cursor):
    data = request.get_json(silent=True) or {}
    key = data.get("key")
    val = data.get("value")
    db_key = GOAL_UI_TO_DB_KEY.get(key)

    if not db_key:
        return jsonify({"status": "error", "message": f"Ungültiger Key: {key}"}), 400

    try:
        val_f = float(val)
        cursor.execute(
            "INSERT INTO goals (key_name, value) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE value = %s",
            (db_key, val_f, val_f),
        )
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/api/tours")
@mysql_connection_wrapper
def api_tours(cursor):
    try:
        ttype_filter = request.args.get("type")
        db_type = get_db_type(ttype_filter)
        month = request.args.get("month")
        year = request.args.get("year")

        sql = (
            "SELECT activity_id, activity_name, activity_date, elapsed_time_s, distance_km "
            "FROM activities WHERE 1=1"
        )
        params = []

        if db_type:
            sql += " AND activity_type = %s"
            params.append(db_type)
        if year:
            sql += " AND YEAR(activity_date) = %s"
            params.append(int(year))
        if month:
            sql += " AND MONTH(activity_date) = %s"
            params.append(int(month))

        sql += " ORDER BY activity_date DESC"
        cursor.execute(sql, params)
        rows = cursor.fetchall() or []

        out = []
        for r in rows:
            dt = r["activity_date"]
            date_disp = dt.strftime("%d.%m.%Y") if isinstance(dt, (date, datetime)) else str(dt)
            dur_s = r["elapsed_time_s"] or 0
            hh, mm = int(dur_s // 3600), int((dur_s % 3600) // 60)

            out.append({
                "id": r["activity_id"],
                "name": r["activity_name"],
                "date_display": date_disp,
                "duration_hm": f"{hh:02d}:{mm:02d}",
                "distance_km": round(float(r["distance_km"] or 0), 2),
            })

        return jsonify(out)
    except Exception as e:
        app.logger.error("FEHLER in api_tours: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
@mysql_connection_wrapper
def api_stats(cursor):
    try:
        ttype_filter = request.args.get("type")
        db_type = get_db_type(ttype_filter)
        month = request.args.get("month")
        year = request.args.get("year")

        try:
            month_i, year_i = int(month), int(year)
        except Exception:
            month_i, year_i = date.today().month, date.today().year

        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())

        sql_m = (
            "SELECT COALESCE(SUM(distance_km),0) AS km, COUNT(*) AS cnt "
            "FROM activities WHERE YEAR(activity_date) = %s AND MONTH(activity_date) = %s"
        )
        params_m = [year_i, month_i]
        if db_type:
            sql_m += " AND activity_type = %s"
            params_m.append(db_type)
        cursor.execute(sql_m, params_m)
        row_m = cursor.fetchone()

        sql_y = (
            "SELECT COALESCE(SUM(distance_km),0) AS km, COUNT(*) AS cnt "
            "FROM activities WHERE YEAR(activity_date) = %s"
        )
        params_y = [year_i]
        if db_type:
            sql_y += " AND activity_type = %s"
            params_y.append(db_type)
        cursor.execute(sql_y, params_y)
        row_y = cursor.fetchone()

        sql_w = (
            "SELECT COALESCE(SUM(distance_km),0) AS km, COUNT(*) AS cnt "
            "FROM activities WHERE activity_date >= %s"
        )
        params_w = [start_of_week]
        if db_type:
            sql_w += " AND activity_type = %s"
            params_w.append(db_type)
        cursor.execute(sql_w, params_w)
        row_w = cursor.fetchone()

        month_names = [
            "Januar", "Februar", "März", "April", "Mai", "Juni",
            "Juli", "August", "September", "Oktober", "November", "Dezember",
        ]

        return jsonify({
            "month_name": month_names[month_i - 1] if 1 <= month_i <= 12 else "",
            "month_km": float(row_m["km"]),
            "month_count": row_m["cnt"],
            "year_km": float(row_y["km"]),
            "year_count": row_y["cnt"],
            "week_km": float(row_w["km"]),
            "week_count": row_w["cnt"],
        })
    except Exception as e:
        app.logger.error("FEHLER in api_stats: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/tours/<int:tour_id>/name", methods=["PUT"])
@mysql_connection_wrapper
def api_update_tour_name(cursor, tour_id):
    try:
        data = request.get_json(silent=True) or {}
        new_name = str(data.get("name", "")).strip()

        if not new_name:
            return jsonify({"status": "error", "message": "Der Tourname darf nicht leer sein."}), 400

        if len(new_name) > 255:
            return jsonify({"status": "error", "message": "Der Tourname ist zu lang."}), 400

        cursor.execute("SELECT activity_id FROM activities WHERE activity_id = %s", (tour_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"status": "error", "message": "Tour nicht gefunden."}), 404

        cursor.execute(
            "UPDATE activities SET activity_name = %s WHERE activity_id = %s",
            (new_name, tour_id),
        )

        return jsonify({
            "status": "ok",
            "tour_id": tour_id,
            "name": new_name,
        })
    except Exception as e:
        app.logger.error("FEHLER beim Umbenennen der Tour %s: %s", tour_id, e)
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/import", methods=["POST"])
@mysql_connection_wrapper
def import_route(cursor):
    """Nimmt hochgeladene GPX-Dateien entgegen und verarbeitet sie."""
    if "files" not in request.files:
        return jsonify({"ok": False, "error": "Keine Dateien gefunden."}), 400

    files = request.files.getlist("files")
    imported_ids = []
    errors = []

    for f in files:
        if not f.filename:
            continue

        filename = secure_filename(f.filename)
        tmp_path = os.path.join(UPLOAD_TMP_DIR, filename)

        try:
            f.save(tmp_path)
            activity_id = process_gpx_file(tmp_path)
            imported_ids.append(activity_id)
        except Exception as e:
            app.logger.error("Fehler beim Import von %s: %s", filename, e)
            errors.append({"filename": filename, "error": str(e)})

    return jsonify({
        "ok": True,
        "imported_count": len(imported_ids),
        "imported_ids": imported_ids,
        "errors": errors,
    })


@app.route("/tour/<int:tour_id>")
@mysql_connection_wrapper
def tour_detail(cursor, tour_id):
    cursor.execute("SELECT * FROM activities WHERE activity_id = %s", (tour_id,))
    row = cursor.fetchone()

    if not row:
        return "Tour nicht gefunden", 404

    filename = row.get("filename")
    gpx_path = os.path.join(GPX_BASE_PATH, filename.replace("/", os.sep)) if filename else ""

    coords = []
    if gpx_path and os.path.exists(gpx_path):
        coords = load_gpx_coords(gpx_path)

    dt = row.get("activity_date")
    dur = row.get("elapsed_time_s") or 0
    hh, mm = int(dur // 3600), int((dur % 3600) // 60)

    tour_data = {
        "id": row["activity_id"],
        "name": row["activity_name"],
        "distance_km": round(float(row["distance_km"] or 0), 2),
        "date_display": dt.strftime("%d.%m.%Y") if isinstance(dt, (date, datetime)) else str(dt),
        "duration_hm": f"{hh:02d}:{mm:02d}",
        "coords": coords,
    }
    return render_template("detail.html", tour=tour_data)


def load_gpx_coords(file_path):
    coords = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            gpx = gpxpy.parse(f)
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        alt = point.elevation if point.elevation is not None else 0.0
                        coords.append([point.latitude, point.longitude, alt])
    except Exception:
        pass
    return coords


if __name__ == "__main__":
    app.run(debug=True)