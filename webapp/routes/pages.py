from flask import Blueprint, current_app, render_template, request, send_from_directory
from datetime import datetime
from ..db.database import mysql_connection_wrapper
from ..services.gpx_utils import load_gpx_data
from ..utils import build_gpx_path, format_date_display, format_duration_hm

pages_bp = Blueprint("pages", __name__)


def _empty_bike_form_data():
    return {
        "id": "",
        "name": "",
        "type": "",
        "init_km": "",
        "marke": "",
        "model": "",
        "startDate": "",
        "endDate": "",
    }


def _load_bikes(cursor):
    cursor.execute(
        """
        SELECT
            b.id,
            b.name,
            b.type,
            b.init_km,
            b.marke,
            b.model,
            b.startDate,
            b.endDate,
            COUNT(DISTINCT bt.activity_id) AS tour_count,
            COALESCE(SUM(a.distance_km), 0) AS km_gefahren
        FROM bikes b
        LEFT JOIN bike_tour bt
            ON bt.bike_id = b.id
        LEFT JOIN activities a
            ON a.activity_id = bt.activity_id
        GROUP BY
            b.id,
            b.name,
            b.type,
            b.init_km,
            b.marke,
            b.model,
            b.startDate,
            b.endDate
        ORDER BY b.name ASC
        """
    )
    return cursor.fetchall()


@pages_bp.route("/")
@mysql_connection_wrapper
def index(cursor):
    # Route für die Startseite (Dashboard)
    now = datetime.now()
    return render_template(
        "index.html",
        current_year=now.year,
        current_month=now.month
    )


@pages_bp.route("/mybikes", methods=["GET", "POST"])
@mysql_connection_wrapper
def mybikes(cursor):
    message = None
    form_data = _empty_bike_form_data()

    if request.method == "POST":
        bike_id = request.form.get("id")
        name = request.form.get("name")
        bike_type = request.form.get("type")
        init_km = request.form.get("init_km") or 0
        marke = request.form.get("marke")
        model = request.form.get("model")
        start_date = request.form.get("startDate") or None
        end_date = request.form.get("endDate") or None

        if bike_id:
            # Update bestehendes Rad
            cursor.execute(
                """
                UPDATE bikes 
                SET name=%s, type=%s, init_km=%s, marke=%s, model=%s, startDate=%s, endDate=%s 
                WHERE id=%s
                """,
                (name, bike_type, init_km, marke, model, start_date, end_date, bike_id),
            )
            message = f"Rad '{name}' wurde aktualisiert."
        else:
            # Neues Rad anlegen
            cursor.execute(
                """
                INSERT INTO bikes (name, type, init_km, marke, model, startDate, endDate) 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (name, bike_type, init_km, marke, model, start_date, end_date),
            )
            message = f"Rad '{name}' wurde neu angelegt."

    bikes = _load_bikes(cursor)
    return render_template(
        "mybikes.html",
        bikes=bikes,
        message=message,
        form_data=form_data
    )


@pages_bp.route("/mygoals")
@mysql_connection_wrapper
def mygoals(cursor):
    # Platzhalter für die Ziele-Seite, um BuildErrors zu vermeiden
    return render_template("mygoals.html")


@pages_bp.route("/static/vendor/<path:filename>")
def custom_static(filename):
    return send_from_directory(current_app.config["VENDOR_STATIC_DIR"], filename)


@pages_bp.route("/tour/<int:tour_id>", methods=["GET"])
@mysql_connection_wrapper
def tour_detail(cursor, tour_id):
    cursor.execute("SELECT * FROM activities WHERE activity_id = %s", (tour_id,))
    row = cursor.fetchone()

    if not row:
        return "Tour nicht gefunden", 404

    bikes = _load_bikes(cursor)

    cursor.execute(
        """
        SELECT bike_id
        FROM bike_tour
        WHERE activity_id = %s
        ORDER BY bike_id ASC
        LIMIT 1
        """,
        (tour_id,),
    )
    bike_link_row = cursor.fetchone() or {}
    selected_bike_id = bike_link_row.get("bike_id")

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
        "date": format_date_display(row["start_time"]),
        "duration": format_duration_hm(row["duration_sec"]),
        "distance": row["distance_km"],
        "avg_speed": row["avg_speed_kmh"],
        "ascent": total_ascent_m or row.get("ascent_m", 0),
        "filename": row["filename"],
    }

    return render_template(
        "tour_detail.html",
        tour=tour_data,
        coords=coords,
        bikes=bikes,
        selected_bike_id=selected_bike_id,
    )