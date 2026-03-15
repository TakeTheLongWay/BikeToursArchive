from datetime import date, datetime

from flask import jsonify, request


def register_tours_routes(app, mysql_connection_wrapper, get_db_type):
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

            tours = []
            for row in rows:
                activity_date = row["activity_date"]
                date_display = (
                    activity_date.strftime("%d.%m.%Y")
                    if isinstance(activity_date, (date, datetime))
                    else str(activity_date)
                )
                duration_s = row["elapsed_time_s"] or 0
                hours = int(duration_s // 3600)
                minutes = int((duration_s % 3600) // 60)

                tours.append(
                    {
                        "id": row["activity_id"],
                        "name": row["activity_name"],
                        "date_display": date_display,
                        "duration_hm": f"{hours:02d}:{minutes:02d}",
                        "distance_km": round(float(row["distance_km"] or 0), 2),
                    }
                )

            return jsonify(tours)
        except Exception as exc:
            app.logger.error("FEHLER in api_tours: %s", exc)
            return jsonify({"error": str(exc)}), 500

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

            return jsonify({"status": "ok", "tour_id": tour_id, "name": new_name})
        except Exception as exc:
            app.logger.error("FEHLER beim Umbenennen der Tour %s: %s", tour_id, exc)
            return jsonify({"status": "error", "message": str(exc)}), 500