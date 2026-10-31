from flask import Blueprint, jsonify

from ..db.database import mysql_connection_wrapper

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
