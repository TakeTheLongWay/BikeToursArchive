import json
import os

from flask import Blueprint, current_app, jsonify, request

from ..db.database import mysql_connection_wrapper
from ..services.gpx_utils import parse_gpx_plan_tracks

collections_bp = Blueprint("collections", __name__)


def _plan_exists_saved(cursor, plan_id):
    """None = Planung gibt es nicht, sonst True/False je nachdem, ob sie schon gespeichert wurde."""
    cursor.execute("SELECT saved_at FROM tour_plans WHERE id = %s", (plan_id,))
    row = cursor.fetchone()
    return None if not row else row["saved_at"] is not None


def _collection_exists(cursor, collection_id):
    cursor.execute("SELECT 1 FROM collections WHERE id = %s", (collection_id,))
    return cursor.fetchone() is not None


# ── GET alle Sammlungen mit Kennzeichen, ob die Planung ihnen zugeordnet ist ──
@collections_bp.route("/api/tour-plans/<int:plan_id>/collections", methods=["GET"])
@mysql_connection_wrapper
def api_tour_plan_collections(cursor, plan_id):
    if _plan_exists_saved(cursor, plan_id) is None:
        return jsonify({"status": "error", "message": "Planung nicht gefunden."}), 404

    cursor.execute(
        """
        SELECT c.id, c.name, ctp.tour_plan_id IS NOT NULL AS assigned
        FROM collections c
        LEFT JOIN collection_tour_plans ctp
            ON ctp.collection_id = c.id AND ctp.tour_plan_id = %s
        ORDER BY c.name ASC
        """,
        (plan_id,),
    )
    collections = [
        {"id": r["id"], "name": r["name"], "assigned": bool(r["assigned"])}
        for r in cursor.fetchall()
    ]
    return jsonify({"status": "ok", "collections": collections})


# ── PUT Planung einer Sammlung zuordnen ──────────────────────────────────────
@collections_bp.route("/api/collections/<int:collection_id>/tour-plans/<int:plan_id>", methods=["PUT"])
@mysql_connection_wrapper
def api_collection_add_plan(cursor, collection_id, plan_id):
    if not _collection_exists(cursor, collection_id):
        return jsonify({"status": "error", "message": "Sammlung nicht gefunden."}), 404
    saved = _plan_exists_saved(cursor, plan_id)
    if saved is None:
        return jsonify({"status": "error", "message": "Planung nicht gefunden."}), 404
    # Nur gespeicherte Tracks haben einen echten Namen; reine Arbeitsstände bleiben außen vor
    if not saved:
        return jsonify({"status": "error", "message": "Den Track zuerst speichern."}), 400

    cursor.execute(
        "INSERT IGNORE INTO collection_tour_plans (collection_id, tour_plan_id) VALUES (%s, %s)",
        (collection_id, plan_id),
    )
    return jsonify({"status": "ok"})


# ── DELETE Zuordnung einer Planung zu einer Sammlung aufheben ────────────────
@collections_bp.route("/api/collections/<int:collection_id>/tour-plans/<int:plan_id>", methods=["DELETE"])
@mysql_connection_wrapper
def api_collection_remove_plan(cursor, collection_id, plan_id):
    cursor.execute(
        "DELETE FROM collection_tour_plans WHERE collection_id = %s AND tour_plan_id = %s",
        (collection_id, plan_id),
    )
    return jsonify({"status": "ok"})


# ── POST externe GPX-Dateien als gespeicherte Tracks importieren und der Sammlung zuordnen ──
@collections_bp.route("/api/collections/<int:collection_id>/import-gpx", methods=["POST"])
@mysql_connection_wrapper
def api_collection_import_gpx(cursor, collection_id):
    if not _collection_exists(cursor, collection_id):
        return jsonify({"status": "error", "message": "Sammlung nicht gefunden."}), 404

    files = [f for f in request.files.getlist("files") if f.filename]
    if not files:
        return jsonify({"status": "error", "message": "Keine Dateien ausgewählt."}), 400

    activities = current_app.config["PLANNING_ACTIVITIES"]
    activity = request.form.get("activity") or next(iter(activities))
    if activity not in activities:
        return jsonify({"status": "error", "message": f"Unbekannte Aktivität: {activity}"}), 400

    # "Planen" setzt die zuletzt bearbeitete Planung fort; importierte Tracks werden daher
    # knapp vor diese einsortiert, damit sie die laufende Planung nicht verdrängen
    cursor.execute("SELECT MAX(updated_at) - INTERVAL 1000 MICROSECOND AS before_current FROM tour_plans")
    before_current = cursor.fetchone()["before_current"]

    imported = []
    errors = []
    for uploaded_file in files:
        filename = os.path.basename(uploaded_file.filename)
        stem, extension = os.path.splitext(filename)
        if extension.lower() != ".gpx":
            errors.append({"filename": filename, "error": "Nur .gpx-Dateien erlaubt."})
            continue

        try:
            plan_tracks = parse_gpx_plan_tracks(
                uploaded_file.read().decode("utf-8-sig"), stem or "Importierter Track", activity
            )
        except Exception as exc:
            current_app.logger.warning("GPX-Import von %s fehlgeschlagen: %s", filename, exc)
            errors.append({"filename": filename, "error": str(exc)})
            continue

        for plan_track in plan_tracks:
            # Import gilt direkt als gespeicherter Stand, damit der Track überall als fertig erscheint
            draft = json.dumps({"track": plan_track["track"]})
            cursor.execute(
                """
                INSERT INTO tour_plans (name, draft, saved_data, saved_at, updated_at)
                VALUES (%s, %s, %s, NOW(), COALESCE(%s, NOW(3)))
                """,
                (plan_track["name"], draft, draft, before_current),
            )
            plan_id = cursor.lastrowid
            cursor.execute(
                "INSERT INTO collection_tour_plans (collection_id, tour_plan_id) VALUES (%s, %s)",
                (collection_id, plan_id),
            )
            imported.append({"id": plan_id, "name": plan_track["name"]})

    return jsonify({"status": "ok", "imported": imported, "errors": errors})
