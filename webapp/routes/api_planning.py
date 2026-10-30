import json
from datetime import datetime

from flask import Blueprint, jsonify, request

from ..db.database import mysql_connection_wrapper

planning_bp = Blueprint("planning", __name__)

PLAN_COLUMNS = "id, name, draft, saved_data, saved_at, created_at, updated_at"


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


def _request_draft():
    data = request.get_json(silent=True) or {}
    draft = data.get("draft")
    return draft if isinstance(draft, dict) else None


# ── GET zuletzt bearbeitete Session (wird beim Öffnen der Seite fortgesetzt) ───
@planning_bp.route("/api/tour-plans/current", methods=["GET"])
@mysql_connection_wrapper
def api_tour_plan_current(cursor):
    cursor.execute(f"SELECT {PLAN_COLUMNS} FROM tour_plans ORDER BY updated_at DESC, id DESC LIMIT 1")
    row = cursor.fetchone()
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
    draft = _request_draft()
    if draft is not None:
        cursor.execute("UPDATE tour_plans SET draft = %s WHERE id = %s", (json.dumps(draft), plan_id))

    cursor.execute(
        "UPDATE tour_plans SET saved_data = draft, saved_at = NOW(), updated_at = NOW(3) WHERE id = %s",
        (plan_id,),
    )
    row = _fetch_plan(cursor, plan_id)
    if not row:
        return jsonify({"status": "error", "message": "Planung nicht gefunden."}), 404
    return jsonify({"status": "ok", "plan": _plan_to_dict(row)})
