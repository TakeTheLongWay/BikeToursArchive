import os
from datetime import date, datetime

from flask import Blueprint, current_app, render_template, send_from_directory

from ..db.database import mysql_connection_wrapper
from ..services.gpx_utils import load_gpx_data

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET"])
def index():
    now = datetime.now()
    return render_template("index.html", current_year=now.year, current_month=now.month)


@pages_bp.route("/mygoals", methods=["GET"])
def mygoals():
    return render_template("mygoals.html")


@pages_bp.route("/vendor/<path:filename>", methods=["GET"])
def vendor_static(filename):
    project_root = os.path.abspath(os.path.join(current_app.root_path, ".."))
    vendor_dir = os.path.join(project_root, "static", "vendor")
    return send_from_directory(vendor_dir, filename)


@pages_bp.route("/tour/<int:tour_id>", methods=["GET"])
@mysql_connection_wrapper
def tour_detail(cursor, tour_id):
    cursor.execute("SELECT * FROM activities WHERE activity_id = %s", (tour_id,))
    row = cursor.fetchone()

    if not row:
        return "Tour nicht gefunden", 404

    filename = row.get("filename")
    gpx_base_path = current_app.config["GPX_BASE_PATH"]
    gpx_path = os.path.join(gpx_base_path, filename.replace("/", os.sep)) if filename else ""

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