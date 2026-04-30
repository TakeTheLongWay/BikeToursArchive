from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request

from ..config import MONTH_NAMES
from ..db.database import mysql_connection_wrapper
from ..utils import get_db_type, is_all_month_selection, parse_month_value, parse_year_value

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/api/stats", methods=["GET"])
@mysql_connection_wrapper
def api_stats(cursor):
    try:
        ttype_filter = request.args.get("type")
        db_type = get_db_type(ttype_filter)
        month = request.args.get("month")
        year = request.args.get("year")

        year_i = parse_year_value(year)
        today = date.today()
        all_months_selected = is_all_month_selection(month)

        if all_months_selected:
            sql_month = (
                "SELECT COALESCE(SUM(distance_km),0) AS km, COUNT(*) AS cnt "
                "FROM activities WHERE YEAR(activity_date) = %s"
            )
            params_month = [year_i]

            if year_i == today.year:
                sql_month += " AND activity_date <= %s"
                params_month.append(today)

            if db_type:
                sql_month += " AND activity_type = %s"
                params_month.append(db_type)

            cursor.execute(sql_month, params_month)
            row_month = cursor.fetchone()
            month_name = "Jahr bis heute" if year_i == today.year else "Alle Monate"
        else:
            month_i = parse_month_value(month)
            sql_month = (
                "SELECT COALESCE(SUM(distance_km),0) AS km, COUNT(*) AS cnt "
                "FROM activities WHERE YEAR(activity_date) = %s AND MONTH(activity_date) = %s"
            )
            params_month = [year_i, month_i]
            if db_type:
                sql_month += " AND activity_type = %s"
                params_month.append(db_type)

            cursor.execute(sql_month, params_month)
            row_month = cursor.fetchone()
            month_name = MONTH_NAMES[month_i - 1] if 1 <= month_i <= 12 else ""

        start_of_week = today - timedelta(days=today.weekday())

        sql_year = (
            "SELECT COALESCE(SUM(distance_km),0) AS km, COUNT(*) AS cnt "
            "FROM activities WHERE YEAR(activity_date) = %s"
        )
        params_year = [year_i]
        if db_type:
            sql_year += " AND activity_type = %s"
            params_year.append(db_type)
        cursor.execute(sql_year, params_year)
        row_year = cursor.fetchone()

        sql_week = (
            "SELECT COALESCE(SUM(distance_km),0) AS km, COUNT(*) AS cnt "
            "FROM activities WHERE activity_date >= %s"
        )
        params_week = [start_of_week]
        if db_type:
            sql_week += " AND activity_type = %s"
            params_week.append(db_type)
        cursor.execute(sql_week, params_week)
        row_week = cursor.fetchone()

        sql_all_rides = (
            "SELECT COALESCE(SUM(distance_km),0) AS km, COUNT(*) AS cnt "
            "FROM activities"
        )
        cursor.execute(sql_all_rides)
        row_all_rides = cursor.fetchone()

        return jsonify(
            {
                "month_name": month_name,
                "month_km": float(row_month["km"]),
                "month_count": row_month["cnt"],
                "year_km": float(row_year["km"]),
                "year_count": row_year["cnt"],
                "week_km": float(row_week["km"]),
                "week_count": row_week["cnt"],
                "all_rides_km": float(row_all_rides["km"]),
                "all_rides_count": row_all_rides["cnt"],
            }
        )
    except Exception as exc:
        current_app.logger.error("FEHLER in api_stats: %s", exc)
        return jsonify({"error": str(exc)}), 500

@stats_bp.route("/api/stats/monthly-comparison", methods=["GET"])
@mysql_connection_wrapper
def api_monthly_comparison(cursor):
    """Liefert Monats-km für zwei Jahre zum Vergleich."""
    try:
        today = date.today()
        year_current = today.year
        year_prev = year_current - 1

        result = {}
        for year in [year_current, year_prev]:
            cursor.execute(
                """
                SELECT MONTH(activity_date) AS month,
                       COALESCE(SUM(distance_km), 0) AS km
                FROM activities
                WHERE YEAR(activity_date) = %s
                GROUP BY MONTH(activity_date)
                ORDER BY MONTH(activity_date)
                """,
                (year,)
            )
            rows = cursor.fetchall()
            monthly = {r["month"]: round(float(r["km"]), 1) for r in rows}
            result[year] = [monthly.get(m, 0) for m in range(1, 13)]

        return jsonify({
            "year_current": year_current,
            "year_prev": year_prev,
            "current": result[year_current],
            "prev": result[year_prev],
            "current_month": today.month,
        })
    except Exception as exc:
        current_app.logger.error("FEHLER in api_monthly_comparison: %s", exc)
        return jsonify({"error": str(exc)}), 500