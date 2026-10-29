from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

from ..config import ACTIVITY_TYPE_ALIASES
from ..db.database import mysql_connection_wrapper

diary_bp = Blueprint("diary", __name__)

# Anzahl Wochen pro Abruf (Nachladen beim Scrollen)
DEFAULT_WEEKS = 12
MAX_WEEKS = 104

# Für die Farbe im Tagebuch: Radfahrten und Touren zu Fuß, alles andere "other".
# Vergleich ohne Groß-/Kleinschreibung wie in MySQL (BikeTracker-GPX liefert z. B. "ebikeride").
CYCLING_TYPES = {t.lower() for t in ACTIVITY_TYPE_ALIASES["cycling"]}
FOOT_TYPES = {"hiking", "hike", "wandern", "spaziergang", "walk"}


def _category(activity_type):
    normalized = (activity_type or "").strip().lower()
    if normalized in CYCLING_TYPES:
        return "cycling"
    if normalized in FOOT_TYPES:
        return "foot"
    return "other"


def _parse_end_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()


def _parse_weeks(value):
    try:
        return max(1, min(int(value), MAX_WEEKS))
    except (TypeError, ValueError):
        return DEFAULT_WEEKS


@diary_bp.route("/api/diary", methods=["GET"])
@mysql_connection_wrapper
def api_diary(cursor):
    """
    Wochen (Mo–So) für das Trainingstagebuch, neueste zuerst: die Woche mit dem Datum end
    und die weeks - 1 Wochen davor, jeweils mit allen Touren je Tag und den Wochensummen.
    """
    try:
        end_date = _parse_end_date(request.args.get("end"))
        weeks = _parse_weeks(request.args.get("weeks"))

        last_monday = end_date - timedelta(days=end_date.weekday())
        range_start = last_monday - timedelta(weeks=weeks - 1)
        range_end = last_monday + timedelta(days=7)

        cursor.execute(
            """
            SELECT
                a.activity_id,
                a.activity_name,
                a.activity_date,
                a.activity_type,
                a.elapsed_time_s,
                a.distance_km,
                a.elevation_gain_m,
                COALESCE(b.name, '') AS bike_name
            FROM activities a
            LEFT JOIN bikes b ON b.id = a.bike_id
            WHERE a.activity_date >= %s AND a.activity_date < %s
            ORDER BY a.activity_date ASC, a.activity_id ASC
            """,
            (range_start, range_end),
        )
        tours_by_day = {}
        for row in cursor.fetchall():
            tours_by_day.setdefault(row["activity_date"].date(), []).append({
                "id": row["activity_id"],
                "name": row["activity_name"],
                "time": row["activity_date"].strftime("%H:%M"),
                "type": row["activity_type"],
                "category": _category(row["activity_type"]),
                "elapsed_s": int(row["elapsed_time_s"] or 0),
                "distance_km": float(row["distance_km"] or 0),
                "elevation_m": float(row["elevation_gain_m"] or 0),
                "bike": row["bike_name"],
            })

        result_weeks = []
        for week_index in range(weeks):
            monday = last_monday - timedelta(weeks=week_index)
            days = []
            totals = {"distance_km": 0.0, "elapsed_s": 0, "elevation_m": 0.0, "count": 0}
            for day_offset in range(7):
                day = monday + timedelta(days=day_offset)
                tours = tours_by_day.get(day, [])
                for tour in tours:
                    totals["distance_km"] += tour["distance_km"]
                    totals["elapsed_s"] += tour["elapsed_s"]
                    totals["elevation_m"] += tour["elevation_m"]
                    totals["count"] += 1
                days.append({"date": day.isoformat(), "tours": tours})

            result_weeks.append({
                "start": monday.isoformat(),
                "iso_week": monday.isocalendar()[1],
                "days": days,
                "totals": totals,
            })

        cursor.execute("SELECT EXISTS(SELECT 1 FROM activities WHERE activity_date < %s) AS has_more", (range_start,))
        has_more = bool(cursor.fetchone()["has_more"])

        return jsonify({
            "weeks": result_weeks,
            "next_end": (range_start - timedelta(days=1)).isoformat(),
            "has_more": has_more,
        })
    except Exception as exc:
        current_app.logger.error("FEHLER in api_diary: %s", exc)
        return jsonify({"error": str(exc)}), 500


@diary_bp.route("/api/diary/years", methods=["GET"])
@mysql_connection_wrapper
def api_diary_years(cursor):
    """Jahre von heute bis zur ältesten Tour (für die Sprungauswahl)."""
    cursor.execute("SELECT MIN(activity_date) AS first_date FROM activities")
    first = cursor.fetchone()["first_date"]
    current_year = date.today().year
    first_year = first.year if first else current_year
    return jsonify(list(range(current_year, first_year - 1, -1)))
