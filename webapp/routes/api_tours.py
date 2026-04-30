import os
from datetime import date

from flask import Blueprint, current_app, jsonify, request, send_file

from ..db.database import mysql_connection_wrapper
from ..utils import (
    format_date_display,
    format_duration_hm,
    get_db_type,
    is_all_month_selection,
    parse_year_value,
)

tours_bp = Blueprint("tours", __name__)


@tours_bp.route("/api/tours", methods=["GET"])
@mysql_connection_wrapper
def api_tours(cursor):
    try:
        ttype_filter = request.args.get("type")
        db_type = get_db_type(ttype_filter)
        month = request.args.get("month")
        year = request.args.get("year")

        sql = (
            "SELECT "
            "a.activity_id, "
            "a.activity_name, "
            "a.activity_date, "
            "a.elapsed_time_s, "
            "a.distance_km, "
            "COALESCE(b.name, '') AS bike_name "
            "FROM activities a "
            "LEFT JOIN bikes b ON b.id = a.bike_id "
            "WHERE 1 = 1"
        )
        params = []

        if db_type:
            sql += " AND a.activity_type = %s"
            params.append(db_type)

        if year:
            year_i = parse_year_value(year)
            sql += " AND YEAR(a.activity_date) = %s"
            params.append(year_i)

            if isAllMonthSelection := is_all_month_selection(month):
                today = date.today()
                if year_i == today.year:
                    sql += " AND a.activity_date <= %s"
                    params.append(today)
            elif month:
                sql += " AND MONTH(a.activity_date) = %s"
                params.append(int(month))
        elif month and not is_all_month_selection(month):
            sql += " AND MONTH(a.activity_date) = %s"
            params.append(int(month))

        sql += " ORDER BY a.activity_date DESC"
        cursor.execute(sql, params)
        rows = cursor.fetchall() or []

        tours = []
        for row in rows:
            tours.append(
                {
                    "id": row["activity_id"],
                    "name": row["activity_name"],
                    "date_display": format_date_display(row["activity_date"]),
                    "duration_hm": format_duration_hm(row["elapsed_time_s"]),
                    "distance_km": round(float(row["distance_km"] or 0), 2),
                    "bike_name": row["bike_name"] or "n/a",
                }
            )

        return jsonify(tours)
    except Exception as exc:
        current_app.logger.error("FEHLER in api_tours: %s", exc)
        return jsonify({"error": str(exc)}), 500


@tours_bp.route("/api/tours/<int:tour_id>/name", methods=["PUT"])
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

        return jsonify({"status": "ok", "tour_id": tour_id, "name": new_name})
    except Exception as exc:
        current_app.logger.error("FEHLER beim Umbenennen der Tour %s: %s", tour_id, exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@tours_bp.route("/api/tours/<int:tour_id>/bike", methods=["PUT"])
@mysql_connection_wrapper
def api_update_tour_bike(cursor, tour_id):
    try:
        data = request.get_json(silent=True) or {}
        bike_id = data.get("bike_id")

        cursor.execute("SELECT activity_id FROM activities WHERE activity_id = %s", (tour_id,))
        activity_row = cursor.fetchone()
        if not activity_row:
            return jsonify({"status": "error", "message": "Tour nicht gefunden."}), 404

        if bike_id in (None, "", "null"):
            cursor.execute(
                "UPDATE activities SET bike_id = NULL WHERE activity_id = %s",
                (tour_id,),
            )
            return jsonify({"status": "ok", "tour_id": tour_id, "bike_id": None})

        try:
            bike_id_int = int(bike_id)
        except (TypeError, ValueError):
            return jsonify({"status": "error", "message": "Ungültige Bike-ID."}), 400

        cursor.execute("SELECT id, name FROM bikes WHERE id = %s", (bike_id_int,))
        bike_row = cursor.fetchone()
        if not bike_row:
            return jsonify({"status": "error", "message": "Bike nicht gefunden."}), 404

        cursor.execute(
            "UPDATE activities SET bike_id = %s WHERE activity_id = %s",
            (bike_id_int, tour_id),
        )

        return jsonify(
            {
                "status": "ok",
                "tour_id": tour_id,
                "bike_id": bike_id_int,
                "bike_name": bike_row["name"],
            }
        )
    except Exception as exc:
        current_app.logger.error("FEHLER beim Speichern des Bikes für Tour %s: %s", tour_id, exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@tours_bp.route("/api/bikes", methods=["GET"])
@mysql_connection_wrapper
def api_bikes(cursor):
    try:
        cursor.execute(
            """
            SELECT
                b.id,
                b.name,
                b.init_km,
                COALESCE(SUM(a.distance_km), 0) AS tour_km
            FROM bikes b
            LEFT JOIN activities a ON a.bike_id = b.id
            WHERE b.endDate IS NULL
            GROUP BY b.id, b.name, b.init_km
            ORDER BY b.name ASC
            """
        )
        rows = cursor.fetchall() or []
        bikes = []
        for row in rows:
            init_km = float(row["init_km"] or 0)
            tour_km = float(row["tour_km"] or 0)
            bikes.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "total_km": round(init_km + tour_km, 1),
                }
            )
        return jsonify(bikes)
    except Exception as exc:
        current_app.logger.error("FEHLER in api_bikes: %s", exc)
        return jsonify({"error": str(exc)}), 500



@tours_bp.route("/api/tours/<int:tour_id>/gpx", methods=["GET"])
@mysql_connection_wrapper
def api_download_gpx(cursor, tour_id):
    try:
        cursor.execute(
            "SELECT activity_name, filename FROM activities WHERE activity_id = %s",
            (tour_id,)
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"status": "error", "message": "Tour nicht gefunden."}), 404

        filename = row.get("filename")
        if not filename:
            return jsonify({"status": "error", "message": "Keine GPX-Datei vorhanden."}), 404

        gpx_base = current_app.config["GPX_BASE_PATH"]
        gpx_path = os.path.join(gpx_base, filename)

        if not os.path.exists(gpx_path):
            return jsonify({"status": "error", "message": "GPX-Datei nicht gefunden."}), 404

        # Dateiname aus Tourname ableiten (Sonderzeichen bereinigen)
        tour_name = row.get("activity_name", f"tour_{tour_id}")
        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in tour_name).strip()
        download_name = f"{safe_name}.gpx"

        return send_file(
            gpx_path,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/gpx+xml",
        )
    except Exception as exc:
        current_app.logger.error("FEHLER beim GPX-Download Tour %s: %s", tour_id, exc)
        return jsonify({"status": "error", "message": str(exc)}), 500


@tours_bp.route("/api/tours/<int:tour_id>", methods=["DELETE"])
@mysql_connection_wrapper
def api_delete_tour(cursor, tour_id):
    try:
        cursor.execute("SELECT activity_id FROM activities WHERE activity_id = %s", (tour_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"status": "error", "message": "Tour nicht gefunden."}), 404

        cursor.execute("DELETE FROM bike_tour WHERE activity_id = %s", (tour_id,))
        cursor.execute("DELETE FROM activities WHERE activity_id = %s", (tour_id,))

        return jsonify({"status": "ok", "tour_id": tour_id})
    except Exception as exc:
        current_app.logger.error("FEHLER beim Löschen der Tour %s: %s", tour_id, exc)
        return jsonify({"status": "error", "message": str(exc)}), 500