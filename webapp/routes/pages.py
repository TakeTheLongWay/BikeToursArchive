from flask import Blueprint, current_app, render_template, send_from_directory

from ..db.database import mysql_connection_wrapper
from ..services.gpx_utils import load_gpx_data
from ..utils import build_gpx_path, format_date_display, format_duration_hm

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET"])
def index():
    from datetime import datetime

    now = datetime.now()
    return render_template("index.html", current_year=now.year, current_month=now.month)


@pages_bp.route("/mygoals", methods=["GET"])
def mygoals():
    return render_template("mygoals.html")


@pages_bp.route("/vendor/<path:filename>", methods=["GET"])
def vendor_static(filename):
    return send_from_directory(current_app.config["VENDOR_STATIC_DIR"], filename)


@pages_bp.route("/tour/<int:tour_id>", methods=["GET"])
@mysql_connection_wrapper
def tour_detail(cursor, tour_id):
    cursor.execute("SELECT * FROM activities WHERE activity_id = %s", (tour_id,))
    row = cursor.fetchone()

    if not row:
        return "Tour nicht gefunden", 404

    gpx_path = build_gpx_path(current_app.config["GPX_BASE_PATH"], row.get("filename"))

    coords = []
    total_ascent_m = 0
    if gpx_path:
        import os

        if os.path.exists(gpx_path):
            coords, total_ascent_m = load_gpx_data(gpx_path)

    tour_data = {
        "id": row["activity_id"],
        "name": row["activity_name"],
        "distance_km": round(float(row["distance_km"] or 0), 2),
        "date_display": format_date_display(row.get("activity_date")),
        "duration_hm": format_duration_hm(row.get("elapsed_time_s")),
        "total_ascent_m": int(round(total_ascent_m)),
        "coords": coords,
    }

    return render_template("detail.html", tour=tour_data)