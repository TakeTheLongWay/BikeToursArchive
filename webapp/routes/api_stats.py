from datetime import date, timedelta

from flask import Blueprint, current_app, jsonify, request

from ..config import MONTH_NAMES
from ..db.database import mysql_connection_wrapper
from ..utils import get_db_type, parse_month_year

stats_bp = Blueprint("stats", __name__)


@stats_bp.route("/api/stats", methods=["GET"])
@mysql_connection_wrapper
def api_stats(cursor):
    try:
        ttype_filter = request.args.get("type")
        db_type = get_db_type(ttype_filter)
        month = request.args.get("month")
        year = request.args.get("year")

        month_i, year_i = parse_month_year(month, year)

        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())

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

        return jsonify(
            {
                "month_name": MONTH_NAMES[month_i - 1] if 1 <= month_i <= 12 else "",
                "month_km": float(row_month["km"]),
                "month_count": row_month["cnt"],
                "year_km": float(row_year["km"]),
                "year_count": row_year["cnt"],
                "week_km": float(row_week["km"]),
                "week_count": row_week["cnt"],
            }
        )
    except Exception as exc:
        current_app.logger.error("FEHLER in api_stats: %s", exc)
        return jsonify({"error": str(exc)}), 500