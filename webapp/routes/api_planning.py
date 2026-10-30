import json
from datetime import datetime

import requests
from flask import Blueprint, current_app, jsonify, request

from ..db.database import PLANNING_SETTINGS, mysql_connection_wrapper

planning_bp = Blueprint("planning", __name__)

PLAN_COLUMNS = "id, name, draft, saved_data, saved_at, created_at, updated_at"
ROUTING_PROFILE_KEY = "planning.routing_profile.{activity}"


def _request_point(data, key):
    """[lat, lon] aus dem Request-Body, None bei fehlendem oder ungültigem Wert."""
    try:
        lat, lon = (float(v) for v in data.get(key))
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


def _routing_profile(cursor, activity):
    key = ROUTING_PROFILE_KEY.format(activity=activity)
    cursor.execute("SELECT setting_value FROM appsettings WHERE setting_key = %s", (key,))
    row = cursor.fetchone()
    profile = str(row["setting_value"] or "").strip() if row else ""
    return profile or PLANNING_SETTINGS[key][0]


# ── POST Route zwischen zwei Trackpunkten entlang von Wegen und Straßen ──────
@planning_bp.route("/api/routing/segment", methods=["POST"])
@mysql_connection_wrapper
def api_routing_segment(cursor):
    data = request.get_json(silent=True) or {}
    start = _request_point(data, "from")
    end = _request_point(data, "to")
    if not start or not end:
        return jsonify({"status": "error", "message": "Start- oder Zielpunkt fehlt oder ist ungültig."}), 400

    activities = current_app.config["PLANNING_ACTIVITIES"]
    activity = data.get("activity") or next(iter(activities))
    if activity not in activities:
        return jsonify({"status": "error", "message": f"Unbekannte Aktivität: {activity}"}), 400

    profile = _routing_profile(cursor, activity)
    response = None
    try:
        response = requests.get(
            current_app.config["BROUTER_URL"],
            params={
                # BRouter erwartet lon,lat
                "lonlats": f"{start[1]},{start[0]}|{end[1]},{end[0]}",
                "profile": profile,
                "alternativeidx": 0,
                "format": "geojson",
            },
            timeout=current_app.config["BROUTER_TIMEOUT_S"],
        )
        response.raise_for_status()
        feature = response.json()["features"][0]
    except (requests.RequestException, ValueError, KeyError, IndexError) as exc:
        # BRouter liefert Fehler (z. B. kein Weg in der Nähe) als Klartext
        detail = response.text.strip()[:200] if response is not None and response.text.strip() else str(exc)
        current_app.logger.warning("Routing fehlgeschlagen (%s): %s", profile, detail)
        return jsonify({"status": "error", "message": f"Routing fehlgeschlagen: {detail}"}), 502

    # [lat, lon, Höhe] je Punkt; Höhe fehlt, wenn BRouter keine liefert
    coords = []
    for point in feature["geometry"]["coordinates"]:
        coord = [round(point[1], 6), round(point[0], 6)]
        if len(point) > 2 and point[2] is not None:
            coord.append(round(point[2], 1))
        coords.append(coord)

    props = feature.get("properties") or {}
    return jsonify({
        "status": "ok",
        "segment": {
            "coords": coords,
            "distance_m": int(props.get("track-length") or 0),
            "ascent_m": int(props.get("filtered ascend") or 0),
            "activity": activity,
            "profile": profile,
        },
    })


def _load_json(value):
    if value is None:
        return None
    return json.loads(value) if isinstance(value, (str, bytes, bytearray)) else value


def _plan_to_dict(row):
    draft = _load_json(row["draft"]) or {}
    saved_data = _load_json(row["saved_data"])
    return {
        "id":         row["id"],
        "name":       row["name"],
        "draft":      draft,
        "saved_at":   str(row["saved_at"]) if row["saved_at"] else "",
        "updated_at": str(row["updated_at"]) if row["updated_at"] else "",
        # Arbeitsstand weicht vom zuletzt gespeicherten Stand ab (oder wurde nie gespeichert)
        "dirty":      draft != saved_data,
    }


def _fetch_plan(cursor, plan_id):
    cursor.execute(f"SELECT {PLAN_COLUMNS} FROM tour_plans WHERE id = %s", (plan_id,))
    return cursor.fetchone()


def _fetch_current_plan(cursor):
    # Aktuell ist die zuletzt bearbeitete (oder geöffnete) Session
    cursor.execute(f"SELECT {PLAN_COLUMNS} FROM tour_plans ORDER BY updated_at DESC, id DESC LIMIT 1")
    return cursor.fetchone()


def _request_draft():
    data = request.get_json(silent=True) or {}
    draft = data.get("draft")
    return draft if isinstance(draft, dict) else None


# ── GET zuletzt bearbeitete Session (wird beim Öffnen der Seite fortgesetzt) ───
@planning_bp.route("/api/tour-plans/current", methods=["GET"])
@mysql_connection_wrapper
def api_tour_plan_current(cursor):
    row = _fetch_current_plan(cursor)
    return jsonify({"status": "ok", "plan": _plan_to_dict(row) if row else None})


# ── GET alle Sessions (Auswahl für "Öffnen"), zuletzt bearbeitete zuerst ─────
@planning_bp.route("/api/tour-plans", methods=["GET"])
@mysql_connection_wrapper
def api_tour_plan_list(cursor):
    cursor.execute(f"SELECT {PLAN_COLUMNS} FROM tour_plans ORDER BY updated_at DESC, id DESC")
    rows = cursor.fetchall() or []
    return jsonify({"status": "ok", "plans": [_plan_to_dict(r) for r in rows]})


# ── POST Session öffnen: wird damit zur zuletzt bearbeiteten (aktuellen) ─────
@planning_bp.route("/api/tour-plans/<int:plan_id>/open", methods=["POST"])
@mysql_connection_wrapper
def api_tour_plan_open(cursor, plan_id):
    cursor.execute("UPDATE tour_plans SET updated_at = NOW(3) WHERE id = %s", (plan_id,))
    row = _fetch_plan(cursor, plan_id)
    if not row:
        return jsonify({"status": "error", "message": "Planung nicht gefunden."}), 404
    return jsonify({"status": "ok", "plan": _plan_to_dict(row)})


# ── POST neue Session anlegen ─────────────────────────────────────────────────
@planning_bp.route("/api/tour-plans", methods=["POST"])
@mysql_connection_wrapper
def api_tour_plan_create(cursor):
    draft = _request_draft() or {}
    name = f"Planung vom {datetime.now():%d.%m.%Y %H:%M}"
    cursor.execute(
        "INSERT INTO tour_plans (name, draft) VALUES (%s, %s)",
        (name, json.dumps(draft)),
    )
    return jsonify({"status": "ok", "plan": _plan_to_dict(_fetch_plan(cursor, cursor.lastrowid))}), 201


# ── PUT Arbeitsstand sichern (automatisch bei jeder Änderung) ────────────────
@planning_bp.route("/api/tour-plans/<int:plan_id>/draft", methods=["PUT"])
@mysql_connection_wrapper
def api_tour_plan_update_draft(cursor, plan_id):
    draft = _request_draft()
    if draft is None:
        return jsonify({"status": "error", "message": "Arbeitsstand fehlt."}), 400

    # updated_at explizit setzen, damit die Session auch ohne inhaltliche Änderung
    # als zuletzt bearbeitet gilt
    cursor.execute(
        "UPDATE tour_plans SET draft = %s, updated_at = NOW(3) WHERE id = %s",
        (json.dumps(draft), plan_id),
    )
    row = _fetch_plan(cursor, plan_id)
    if not row:
        return jsonify({"status": "error", "message": "Planung nicht gefunden."}), 404
    return jsonify({"status": "ok", "plan": _plan_to_dict(row)})


# ── POST Arbeitsstand als gespeicherten Stand festschreiben ──────────────────
@planning_bp.route("/api/tour-plans/<int:plan_id>/save", methods=["POST"])
@mysql_connection_wrapper
def api_tour_plan_save(cursor, plan_id):
    row = _fetch_plan(cursor, plan_id)
    if not row:
        return jsonify({"status": "error", "message": "Planung nicht gefunden."}), 404

    # Beim ersten Speichern bekommt der Track einen Namen; danach ist er optional
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    if not name and not row["saved_at"]:
        return jsonify({"status": "error", "message": "Bitte einen Namen für den Track angeben."}), 400
    if len(name) > 255:
        return jsonify({"status": "error", "message": "Der Name ist zu lang (max. 255 Zeichen)."}), 400
    if name:
        cursor.execute("UPDATE tour_plans SET name = %s WHERE id = %s", (name, plan_id))

    draft = _request_draft()
    if draft is not None:
        cursor.execute("UPDATE tour_plans SET draft = %s WHERE id = %s", (json.dumps(draft), plan_id))

    cursor.execute(
        "UPDATE tour_plans SET saved_data = draft, saved_at = NOW(), updated_at = NOW(3) WHERE id = %s",
        (plan_id,),
    )
    return jsonify({"status": "ok", "plan": _plan_to_dict(_fetch_plan(cursor, plan_id))})


# ── DELETE Session entfernen; liefert die danach aktuelle Session (oder null) ─
@planning_bp.route("/api/tour-plans/<int:plan_id>", methods=["DELETE"])
@mysql_connection_wrapper
def api_tour_plan_delete(cursor, plan_id):
    cursor.execute("DELETE FROM tour_plans WHERE id = %s", (plan_id,))
    if not cursor.rowcount:
        return jsonify({"status": "error", "message": "Planung nicht gefunden."}), 404

    row = _fetch_current_plan(cursor)
    return jsonify({"status": "ok", "plan": _plan_to_dict(row) if row else None})
