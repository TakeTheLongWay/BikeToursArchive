from datetime import date, timedelta

from flask import jsonify, request


def register_stats_routes(app, mysql_connection_wrapper, get_db_type):
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
                "Januar",
                "Februar",
                "März",
                "April",
                "Mai",
                "Juni",
                "Juli",
                "August",
                "September",
                "Oktober",
                "November",
                "Dezember",
            ]

            return jsonify(
                {
                    "month_name": month_names[month_i - 1] if 1 <= month_i <= 12 else "",
                    "month_km": float(row_m["km"]),
                    "month_count": row_m["cnt"],
                    "year_km": float(row_y["km"]),
                    "year_count": row_y["cnt"],
                    "week_km": float(row_w["km"]),
                    "week_count": row_w["cnt"],
                }
            )
        except Exception as exc:
            app.logger.error("FEHLER in api_stats: %s", exc)
            return jsonify({"error": str(exc)}), 500