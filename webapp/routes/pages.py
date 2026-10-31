import io
import json
import mimetypes
import mysql.connector
from flask import Blueprint, current_app, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for
from datetime import date, datetime
from ..db.database import HOMEBASE_SETTINGS, mysql_connection_wrapper
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


@pages_bp.route("/tagebuch")
def diary():
    return render_template("diary.html")


@pages_bp.route("/statistik")
def statistics():
    return render_template("statistics.html")


@pages_bp.route("/tourplanung")
@mysql_connection_wrapper
def tour_planning(cursor):
    cursor.execute(
        "SELECT setting_key, setting_value FROM appsettings WHERE setting_key IN (%s, %s, %s)",
        tuple(HOMEBASE_SETTINGS),
    )
    values = {row["setting_key"]: row["setting_value"] for row in cursor.fetchall()}

    # Fehlende oder ungültige Einträge fallen auf den Startwert zurück
    def setting(key, convert):
        try:
            return convert(str(values[key]).strip().replace(",", "."))
        except (KeyError, ValueError):
            return convert(HOMEBASE_SETTINGS[key][0])

    homebase = {
        "lat": setting("homebase.lat", float),
        "lon": setting("homebase.lon", float),
        "zoom": setting("homebase.zoom", int),
    }
    return render_template(
        "tour_planning.html",
        homebase=homebase,
        activities=current_app.config["PLANNING_ACTIVITIES"],
        # ?plan=<id> z. B. aus einer Sammlung: diese Planung statt der zuletzt bearbeiteten öffnen
        open_plan_id=request.args.get("plan", type=int),
    )


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


@pages_bp.route("/api/tours/<int:tour_id>/media/<path:filename>/caption", methods=["PUT"])
@mysql_connection_wrapper
def api_update_media_caption(cursor, tour_id, filename):
    try:
        data = request.get_json(silent=True) or {}
        # Leerer Text entfernt die Bildunterschrift (NULL, wie beim Import)
        caption = str(data.get("caption", "")).strip() or None

        cursor.execute("SELECT media FROM activities WHERE activity_id = %s", (tour_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"status": "error", "message": "Tour nicht gefunden."}), 404
        if filename not in _tour_media_filenames(row["media"]):
            return jsonify({"status": "error", "message": "Bild gehört nicht zu dieser Tour."}), 404

        # Zeile anlegen, falls das Bild noch keinen Eintrag in media hat
        cursor.execute(
            """
            INSERT INTO media (filename, caption) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE caption = VALUES(caption)
            """,
            (filename, caption),
        )

        return jsonify({"status": "ok", "filename": filename, "caption": caption or ""})
    except Exception as exc:
        current_app.logger.error("FEHLER beim Speichern der Bildunterschrift %s: %s", filename, exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


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
    # Alle Bilder und Videos aller Touren, neueste Tour zuerst
    cursor.execute(
        """
        SELECT activity_id, activity_name, activity_date, media FROM activities
        WHERE media IS NOT NULL AND media <> ''
        ORDER BY activity_date DESC, activity_id DESC
        """
    )
    rows = cursor.fetchall()

    cursor.execute("SELECT filename, caption FROM media WHERE caption IS NOT NULL AND caption <> ''")
    captions = {r["filename"]: r["caption"] for r in cursor.fetchall()}

    # Nach Jahren gruppiert (Zwischenüberschriften); rows sind bereits absteigend sortiert
    years = []
    images = []
    for row in rows:
        activity_date = row["activity_date"]
        year = activity_date.year if isinstance(activity_date, (date, datetime)) else str(activity_date)[:4]
        if not years or years[-1]["year"] != year:
            years.append({"year": year, "images": []})
        images = years[-1]["images"]

        tour = {
            "id": row["activity_id"],
            "name": row["activity_name"],
            "date_display": format_date_display(row["activity_date"]),
        }
        # index = Position in der Medienliste der Tour, damit die Bilderseite
        # beim Klick direkt dieses Bild/Video zeigt
        for index, filename in enumerate(_tour_media_filenames(row["media"])):
            images.append({
                "filename": filename,
                "index": index,
                "caption": captions.get(filename) or "",
                "is_video": filename.lower().endswith(VIDEO_EXTENSIONS),
                "tour": tour,
            })

    years = [group for group in years if group["images"]]
    all_images = [image for group in years for image in group["images"]]
    video_count = sum(1 for image in all_images if image["is_video"])
    return render_template(
        "gallery.html",
        years=years,
        image_count=len(all_images) - video_count,
        video_count=video_count,
    )


COLLECTION_IMAGE_MAX_BYTES = 10 * 1024 * 1024


@pages_bp.route("/sammlungen", methods=["GET", "POST"])
@mysql_connection_wrapper
def collections(cursor):
    error = None
    form_name = ""

    if request.method == "POST":
        form_name = (request.form.get("name") or "").strip()
        upload = request.files.get("image")
        image = upload.read() if upload and upload.filename else None
        image_mimetype = None
        if image:
            image_mimetype = upload.mimetype or mimetypes.guess_type(upload.filename)[0]

        if not form_name:
            error = "Bitte einen Namen für die Sammlung eingeben."
        elif image and not (image_mimetype or "").startswith("image/"):
            error = "Die hochgeladene Datei ist kein Bild."
        elif image and len(image) > COLLECTION_IMAGE_MAX_BYTES:
            error = "Das Bild ist zu groß (max. 10 MB)."
        else:
            try:
                cursor.execute(
                    "INSERT INTO collections (name, image, image_mimetype) VALUES (%s, %s, %s)",
                    (form_name, image, image_mimetype),
                )
            except mysql.connector.IntegrityError:
                error = f"Eine Sammlung '{form_name}' gibt es bereits."
            else:
                # Post/Redirect/Get, damit ein Neuladen die Sammlung nicht doppelt anlegt
                return redirect(url_for("pages.collections"))

    cursor.execute(
        """
        SELECT c.id, c.name, c.image IS NOT NULL AS has_image, COUNT(ctp.tour_plan_id) AS track_count
        FROM collections c
        LEFT JOIN collection_tour_plans ctp ON ctp.collection_id = c.id
        GROUP BY c.id, c.name, has_image
        ORDER BY c.name ASC
        """
    )
    return render_template(
        "collections.html",
        collections=cursor.fetchall(),
        error=error,
        form_name=form_name,
    )


def _plan_track_summary(row):
    # Kennzahlen aus dem gespeicherten Stand der Planung (ohne Speicherung: Arbeitsstand)
    data = row["saved_data"] if row["saved_data"] is not None else row["draft"]
    if isinstance(data, (str, bytes, bytearray)):
        data = json.loads(data)
    track = (data or {}).get("track") or {}
    segments = track.get("segments") or []
    activities = current_app.config["PLANNING_ACTIVITIES"]
    return {
        "id": row["id"],
        "name": row["name"],
        "activity": activities.get(track.get("activity"), ""),
        "distance_km": sum(seg.get("distance_m") or 0 for seg in segments) / 1000,
        "ascent_m": sum(seg.get("ascent_m") or 0 for seg in segments),
        "saved_display": format_date_display(row["saved_at"]) if row["saved_at"] else "",
    }


@pages_bp.route("/sammlungen/<int:collection_id>")
@mysql_connection_wrapper
def collection_detail(cursor, collection_id):
    cursor.execute(
        "SELECT id, name, image IS NOT NULL AS has_image FROM collections WHERE id = %s",
        (collection_id,),
    )
    collection = cursor.fetchone()
    if not collection:
        return "Sammlung nicht gefunden", 404

    cursor.execute(
        """
        SELECT p.id, p.name, p.draft, p.saved_data, p.saved_at
        FROM collection_tour_plans ctp
        JOIN tour_plans p ON p.id = ctp.tour_plan_id
        WHERE ctp.collection_id = %s
        ORDER BY p.name ASC
        """,
        (collection_id,),
    )
    tracks = [_plan_track_summary(row) for row in cursor.fetchall()]

    # Auswahl zum Hinzufügen: gespeicherte Tracks, die noch nicht in der Sammlung liegen
    cursor.execute(
        """
        SELECT p.id, p.name FROM tour_plans p
        WHERE p.saved_at IS NOT NULL
          AND p.id NOT IN (SELECT tour_plan_id FROM collection_tour_plans WHERE collection_id = %s)
        ORDER BY p.name ASC
        """,
        (collection_id,),
    )
    return render_template(
        "collection_detail.html",
        collection=collection,
        tracks=tracks,
        available_plans=cursor.fetchall(),
    )


@pages_bp.route("/sammlungen/<int:collection_id>/bild")
@mysql_connection_wrapper
def collection_image(cursor, collection_id):
    cursor.execute("SELECT image, image_mimetype FROM collections WHERE id = %s", (collection_id,))
    row = cursor.fetchone()
    if not row or not row["image"]:
        return "Bild nicht gefunden", 404

    return send_file(
        io.BytesIO(row["image"]),
        mimetype=row["image_mimetype"] or "application/octet-stream",
    )


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
        "calories_calc": row.get("calories_calc"),
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