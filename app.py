import logging
import os
from datetime import date, datetime

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

from api_goals import register_goals_routes
from api_stats import register_stats_routes
from api_tours import register_tours_routes
from database import ensure_database, mysql_connection_wrapper
from gpx_utils import load_gpx_data
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

VALID_GOAL_DB_KEYS = {"goal_km_year", "monthly", "weekly", "daily"}


def get_db_type(filter_type):
    """Übersetzt Dashboard-Filter in DB-Typen (activity_type)."""
    if filter_type == "Alle" or not filter_type:
        return None
    if filter_type == "per pedes":
        return "hiking"
    return filter_type


register_goals_routes(
    app=app,
    mysql_connection_wrapper=mysql_connection_wrapper,
    goal_ui_to_db_key=GOAL_UI_TO_DB_KEY,
    valid_goal_db_keys=VALID_GOAL_DB_KEYS,
)

register_tours_routes(
    app=app,
    mysql_connection_wrapper=mysql_connection_wrapper,
    get_db_type=get_db_type,
)

register_stats_routes(
    app=app,
    mysql_connection_wrapper=mysql_connection_wrapper,
    get_db_type=get_db_type,
)


@app.route("/")
def index():
    now = datetime.now()
    return render_template("index.html", current_year=now.year, current_month=now.month)


@app.route("/mygoals")
def mygoals():
    return render_template("mygoals.html")


@app.route("/import", methods=["POST"])
@mysql_connection_wrapper
def import_route(cursor):
    """Nimmt hochgeladene GPX-Dateien entgegen und verarbeitet sie."""
    del cursor

    if "files" not in request.files:
        return jsonify({"ok": False, "error": "Keine Dateien gefunden."}), 400

    files = request.files.getlist("files")
    imported_ids = []
    errors = []

    for uploaded_file in files:
        if not uploaded_file.filename:
            continue

        filename = secure_filename(uploaded_file.filename)
        tmp_path = os.path.join(UPLOAD_TMP_DIR, filename)

        try:
            uploaded_file.save(tmp_path)
            activity_id = process_gpx_file(tmp_path)
            imported_ids.append(activity_id)
        except Exception as exc:
            app.logger.error("Fehler beim Import von %s: %s", filename, exc)
            errors.append({"filename": filename, "error": str(exc)})

    return jsonify(
        {
            "ok": True,
            "imported_count": len(imported_ids),
            "imported_ids": imported_ids,
            "errors": errors,
        }
    )


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
    total_ascent_m = 0
    if gpx_path and os.path.exists(gpx_path):
        coords, total_ascent_m = load_gpx_data(gpx_path)

    activity_date = row.get("activity_date")
    duration_s = row.get("elapsed_time_s") or 0
    hours = int(duration_s // 3600)
    minutes = int((duration_s % 3600) // 60)

    tour_data = {
        "id": row["activity_id"],
        "name": row["activity_name"],
        "distance_km": round(float(row["distance_km"] or 0), 2),
        "date_display": (
            activity_date.strftime("%d.%m.%Y")
            if isinstance(activity_date, (date, datetime))
            else str(activity_date)
        ),
        "duration_hm": f"{hours:02d}:{minutes:02d}",
        "total_ascent_m": int(round(total_ascent_m)),
        "coords": coords,
    }
    return render_template("detail.html", tour=tour_data)


if __name__ == "__main__":
    app.run(debug=True)