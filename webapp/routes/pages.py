from flask import Blueprint, current_app, render_template, request, send_from_directory

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
    }


def _load_bikes(cursor):
    cursor.execute(
        """
        SELECT id, name, type, init_km, marke, model
        FROM bikes
        ORDER BY name ASC, id ASC
        """
    )
    rows = cursor.fetchall() or []

    bikes = []
    for row in rows:
        bikes.append(
            {
                "id": row["id"],
                "name": row["name"] or "",
                "type": row["type"] or "",
                "init_km": float(row["init_km"] or 0),
                "marke": row["marke"] or "",
                "model": row["model"] or "",
            }
        )
    return bikes


@pages_bp.route("/", methods=["GET"])
def index():
    from datetime import datetime

    now = datetime.now()
    return render_template("index.html", current_year=now.year, current_month=now.month)


@pages_bp.route("/mygoals", methods=["GET"])
def mygoals():
    return render_template("mygoals.html")


@pages_bp.route("/mybikes", methods=["GET"])
@mysql_connection_wrapper
def mybikes(cursor):
    bikes = _load_bikes(cursor)
    return render_template(
        "mybikes.html",
        form_data=_empty_bike_form_data(),
        bikes=bikes,
        error_message=None,
        success_message=None,
    )


@pages_bp.route("/mybikes", methods=["POST"])
@mysql_connection_wrapper
def mybikes_save(cursor):
    form_data = {
        "id": (request.form.get("id") or "").strip(),
        "name": (request.form.get("name") or "").strip(),
        "type": (request.form.get("type") or "").strip(),
        "init_km": (request.form.get("init_km") or "").strip(),
        "marke": (request.form.get("marke") or "").strip(),
        "model": (request.form.get("model") or "").strip(),
    }

    if not form_data["name"]:
        return render_template(
            "mybikes.html",
            form_data=form_data,
            bikes=_load_bikes(cursor),
            error_message="Bitte gib einen Namen für das Bike ein.",
            success_message=None,
        )

    if not form_data["type"]:
        return render_template(
            "mybikes.html",
            form_data=form_data,
            bikes=_load_bikes(cursor),
            error_message="Bitte gib einen Typ für das Bike ein.",
            success_message=None,
        )

    try:
        init_km = float(form_data["init_km"].replace(",", ".")) if form_data["init_km"] else 0.0
    except ValueError:
        return render_template(
            "mybikes.html",
            form_data=form_data,
            bikes=_load_bikes(cursor),
            error_message="Bitte gib für den Start-km-Stand eine gültige Zahl ein.",
            success_message=None,
        )

    if init_km < 0:
        return render_template(
            "mybikes.html",
            form_data=form_data,
            bikes=_load_bikes(cursor),
            error_message="Der Start-km-Stand darf nicht negativ sein.",
            success_message=None,
        )

    marke = form_data["marke"] or None
    model = form_data["model"] or None

    if form_data["id"]:
        try:
            bike_id = int(form_data["id"])
        except ValueError:
            return render_template(
                "mybikes.html",
                form_data=form_data,
                bikes=_load_bikes(cursor),
                error_message="Ungültige Bike-ID.",
                success_message=None,
            )

        cursor.execute("SELECT id FROM bikes WHERE id = %s", (bike_id,))
        existing_row = cursor.fetchone()
        if not existing_row:
            return render_template(
                "mybikes.html",
                form_data=form_data,
                bikes=_load_bikes(cursor),
                error_message="Das ausgewählte Bike wurde nicht gefunden.",
                success_message=None,
            )

        cursor.execute(
            """
            UPDATE bikes
            SET name = %s,
                type = %s,
                init_km = %s,
                marke = %s,
                model = %s
            WHERE id = %s
            """,
            (form_data["name"], form_data["type"], init_km, marke, model, bike_id),
        )

        success_message = f'Bike "{form_data["name"]}" wurde erfolgreich aktualisiert.'
    else:
        cursor.execute(
            """
            INSERT INTO bikes (name, type, init_km, marke, model)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (form_data["name"], form_data["type"], init_km, marke, model),
        )

        success_message = f'Bike "{form_data["name"]}" wurde erfolgreich gespeichert.'

    bikes = _load_bikes(cursor)

    return render_template(
        "mybikes.html",
        form_data=_empty_bike_form_data(),
        bikes=bikes,
        error_message=None,
        success_message=success_message,
    )


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