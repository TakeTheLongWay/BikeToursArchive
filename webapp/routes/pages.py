import io
import mimetypes
from flask import Blueprint, current_app, render_template, request, send_file, send_from_directory
from datetime import datetime
from ..db.database import mysql_connection_wrapper
from ..services.biketracker_source import BikeTrackerSourceError, get_source
from ..services.track_files import load_track_data, track_extension
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
            COUNT(DISTINCT a.activity_id) AS tour_count,
            COALESCE(SUM(a.distance_km), 0) AS km_gefahren
        FROM bikes b
        LEFT JOIN activities a
            ON a.bike_id = b.id
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
    now = datetime.now()
    return render_template(
        "index.html",
        current_year=now.year,
        current_month=now.month
    )

@pages_bp.route("/appsettings")
def appsettings():
    return render_template("appsettings.html")


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
    return render_template("mygoals.html")


@pages_bp.route("/kmyear")
def kmyear():
    return render_template("km_year.html")


@pages_bp.route("/kmcurves")
def kmcurves():
    return render_template("km_curves.html")


@pages_bp.route("/static/vendor/<path:filename>")
def vendor_static(filename):
    # Name der Funktion auf 'vendor_static' geändert, passend zum url_for im Template
    return send_from_directory(current_app.config["VENDOR_STATIC_DIR"], filename)


VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm")


def _tour_media_filenames(media_value):
    # activities.media aus dem Strava-Export: "media/a.jpg|media/b.mp4"; gespeichert wird
    # in der Tabelle media nur der Dateiname ohne "media/"
    filenames = []
    for part in (media_value or "").split("|"):
        filename = part.strip().rsplit("/", 1)[-1]
        if filename:
            filenames.append(filename)
    return filenames


def _load_tour_media(cursor, media_value):
    filenames = _tour_media_filenames(media_value)
    if not filenames:
        return []

    placeholders = ", ".join(["%s"] * len(filenames))
    cursor.execute(f"SELECT filename, caption FROM media WHERE filename IN ({placeholders})", filenames)
    captions = {r["filename"]: r["caption"] for r in cursor.fetchall()}

    # Reihenfolge wie in activities.media
    return [
        {
            "filename": filename,
            "caption": captions.get(filename) or "",
            "is_video": filename.lower().endswith(VIDEO_EXTENSIONS),
        }
        for filename in filenames
    ]


@pages_bp.route("/tour-media/<path:filename>")
def tour_media_file(filename):
    # Bild/Video aus dem BikeTracker-Unterordner images (Drive-API oder lokal, je nach BIKETRACKER_SOURCE)
    try:
        data = get_source().read_media(filename)
    except BikeTrackerSourceError as exc:
        current_app.logger.error("Tourbild %s nicht ladbar: %s", filename, exc)
        return str(exc), 404

    # conditional=True erlaubt Range-Anfragen (Spulen in Videos); die Dateien ändern sich nicht,
    # daher darf der Browser sie lange zwischenspeichern
    return send_file(
        io.BytesIO(data),
        mimetype=mimetypes.guess_type(filename)[0] or "application/octet-stream",
        download_name=filename,
        conditional=True,
        max_age=30 * 24 * 3600,
    )


@pages_bp.route("/tour/<int:tour_id>/bilder", methods=["GET"])
@mysql_connection_wrapper
def tour_media(cursor, tour_id):
    cursor.execute(
        "SELECT activity_id, activity_name, activity_date, media FROM activities WHERE activity_id = %s",
        (tour_id,),
    )
    row = cursor.fetchone()

    if not row:
        return "Tour nicht gefunden", 404

    return render_template(
        "tour_media.html",
        tour={
            "id": row["activity_id"],
            "name": row["activity_name"],
            "date_display": format_date_display(row["activity_date"]),
        },
        media=_load_tour_media(cursor, row["media"]),
        # ?bild=<index> aus der Galerie; ohne Angabe beginnt die Seite mit dem ersten Bild
        start_index=request.args.get("bild", 0, type=int),
    )


@pages_bp.route("/galerie", methods=["GET"])
@mysql_connection_wrapper
def gallery(cursor):
    # Alle Bilder (ohne Videos) aller Touren, neueste Tour zuerst
    cursor.execute(
        """
        SELECT activity_id, activity_name, activity_date, media FROM activities
        WHERE media IS NOT NULL AND media <> ''
        ORDER BY activity_date DESC, activity_id DESC
        """
    )
    images = []
    for row in cursor.fetchall():
        tour = {
            "id": row["activity_id"],
            "name": row["activity_name"],
            "date_display": format_date_display(row["activity_date"]),
        }
        # index = Position in der Medienliste der Tour (mit Videos), damit die Bilderseite
        # beim Klick direkt dieses Bild zeigt
        for index, filename in enumerate(_tour_media_filenames(row["media"])):
            if not filename.lower().endswith(VIDEO_EXTENSIONS):
                images.append({"filename": filename, "index": index, "tour": tour})

    return render_template("gallery.html", images=images)


@pages_bp.route("/tour/<int:tour_id>", methods=["GET"])
@mysql_connection_wrapper
def tour_detail(cursor, tour_id):
    cursor.execute("SELECT * FROM activities WHERE activity_id = %s", (tour_id,))
    row = cursor.fetchone()

    if not row:
        return "Tour nicht gefunden", 404

    cursor.execute(
        "SELECT bike_id FROM activities WHERE activity_id = %s",
        (tour_id,),
    )
    bike_link_row = cursor.fetchone() or {}
    selected_bike_id = bike_link_row.get("bike_id")

    # Nur aktive Bikes (ohne endDate) anbieten; das aktuell zugeordnete Bike bleibt sichtbar
    bikes = [
        bike for bike in _load_bikes(cursor)
        if not bike.get("endDate") or bike["id"] == selected_bike_id
    ]

    # Blättern: datumsmäßig vorherige/nächste Tour (activity_id entscheidet bei gleichem Datum)
    cursor.execute(
        """
        SELECT activity_id FROM activities
        WHERE activity_date < %s OR (activity_date = %s AND activity_id < %s)
        ORDER BY activity_date DESC, activity_id DESC
        LIMIT 1
        """,
        (row["activity_date"], row["activity_date"], tour_id),
    )
    prev_row = cursor.fetchone()
    cursor.execute(
        """
        SELECT activity_id FROM activities
        WHERE activity_date > %s OR (activity_date = %s AND activity_id > %s)
        ORDER BY activity_date ASC, activity_id ASC
        LIMIT 1
        """,
        (row["activity_date"], row["activity_date"], tour_id),
    )
    next_row = cursor.fetchone()

    track_path = build_gpx_path(current_app.config["GPX_BASE_PATH"], row.get("filename"))

    coords = []
    total_ascent_m = 0
    if track_path:
        import os
        if os.path.exists(track_path):
            coords, total_ascent_m = load_track_data(track_path)

    # Dictionary-Keys an detail.html angepasst
    tour_data = {
        "id": row["activity_id"],
        "name": row["activity_name"],
        "date_display": format_date_display(row["activity_date"]),
        "duration_hm": format_duration_hm(row["elapsed_time_s"]),
        "distance_km": row["distance_km"],
        "total_ascent_m": total_ascent_m or float(row.get("elevation_gain_m") or 0),
        "temp_min_c": row.get("temp_min_c"),
        "temp_max_c": row.get("temp_max_c"),
        # Zusatzwerte aus TCX-Dateien (bei GPX-Touren meist leer)
        "moving_time_hm": format_duration_hm(row["moving_time_s"]) if row.get("moving_time_s") else None,
        "max_speed_kmh": row.get("max_speed_kmh"),
        "avg_watts": row.get("avg_watts"),
        "max_watts": row.get("max_watts"),
        "avg_cadence_rpm": row.get("avg_cadence_rpm"),
        "max_cadence_rpm": row.get("max_cadence_rpm"),
        "calories": row.get("calories"),
        "min_elevation_m": row.get("min_elevation_m"),
        "max_elevation_m": row.get("max_elevation_m"),
        "device_name": row.get("device_name"),
        "filename": row["filename"],
        "file_format": track_extension(row["filename"]).lstrip(".").upper() or "GPX",
        "prev_id": prev_row["activity_id"] if prev_row else None,
        "next_id": next_row["activity_id"] if next_row else None,
        "has_media": bool(_tour_media_filenames(row.get("media"))),
        "coords": coords, # Coords direkt ins Tour-Objekt für das Template
    }

    return render_template(
        "detail.html", # Korrigierter Name der Template-Datei
        tour=tour_data,
        bikes=bikes,
        selected_bike_id=selected_bike_id,
    )