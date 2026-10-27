import os
import uuid

import mysql.connector
from flask import Blueprint, current_app, jsonify, render_template, request

from ..db.database import get_db_connection
from ..services.biketracker_source import BikeTrackerSourceError, get_source
from ..services.importer import DuplicateActivityError, process_track_file

biketracker_bp = Blueprint("biketracker", __name__)


def _load_imports(file_ids: list) -> dict:
    """Liefert {file_id: {"activity_id", "imported_at"}} für bereits importierte Dateien."""
    if not file_ids:
        return {}

    placeholders = ", ".join(["%s"] * len(file_ids))
    conn = get_db_connection()
    cur = conn.cursor(dictionary=True)
    try:
        # Nur Touren, die noch existieren; gelöschte Touren gelten wieder als nicht importiert
        cur.execute(
            f"""
            SELECT bi.file_id, bi.activity_id, bi.imported_at
            FROM biketracker_imports bi
            JOIN activities a ON a.activity_id = bi.activity_id
            WHERE bi.file_id IN ({placeholders})
            """,
            tuple(file_ids),
        )
        return {row["file_id"]: row for row in cur.fetchall()}
    finally:
        cur.close()
        conn.close()


def _record_import(file_id: str, filename: str, activity_id: int) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO biketracker_imports (file_id, filename, activity_id)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                filename = VALUES(filename),
                activity_id = VALUES(activity_id),
                imported_at = CURRENT_TIMESTAMP
            """,
            (file_id, filename, activity_id),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def _delete_import(file_id: str) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM biketracker_imports WHERE file_id = %s", (file_id,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


@biketracker_bp.route("/biketracker", methods=["GET"])
def biketracker():
    source = get_source()
    files = []
    error = None

    try:
        files = source.list_latest_files(current_app.config["BIKETRACKER_MAX_FILES"])
    except BikeTrackerSourceError as exc:
        current_app.logger.error("BikeTracker-Quelle nicht lesbar (%s): %s", source.label, exc)
        error = str(exc)

    try:
        imports = _load_imports([f["id"] for f in files])
    except mysql.connector.Error as exc:
        current_app.logger.error("Importstatus der BikeTracker-Dateien nicht lesbar: %s", exc)
        imports = {}

    for f in files:
        f["import"] = imports.get(f["id"])

    return render_template("biketracker.html", files=files, source_label=source.label, error=error)


@biketracker_bp.route("/biketracker/import", methods=["POST"])
def biketracker_import():
    payload = request.get_json(silent=True) or {}
    file_ids = payload.get("files") or []
    if not file_ids:
        return jsonify({"ok": False, "error": "Keine Dateien ausgewählt."}), 400

    source = get_source()
    upload_tmp_dir = current_app.config["UPLOAD_TMP_DIR"]
    imported_ids = []
    duplicates = []
    errors = []

    for file_id in file_ids:
        # Kopie importieren, da process_track_file die Quelldatei entfernt;
        # das Format (GPX/TCX) ergibt sich aus dem Originaldateinamen
        tmp_path = os.path.join(upload_tmp_dir, f"biketracker_{uuid.uuid4().hex}.tmp")
        filename = file_id
        activity_id = None
        try:
            filename = source.download(file_id, tmp_path)
            activity_id = process_track_file(tmp_path, filename)
            imported_ids.append(activity_id)
        except DuplicateActivityError as exc:
            # Tour ist schon vorhanden: Datei ebenfalls als importiert merken
            activity_id = exc.activity_id
            duplicates.append({"filename": filename, "activity_id": exc.activity_id, "activity_name": exc.activity_name})
            os.remove(tmp_path)
        except Exception as exc:
            current_app.logger.error("Fehler beim BikeTracker-Import von %s: %s", filename, exc)
            errors.append({"filename": filename, "error": str(exc)})
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        if activity_id is not None:
            try:
                _record_import(file_id, filename, activity_id)
            except mysql.connector.Error as exc:
                current_app.logger.error("Importstatus für %s nicht gespeichert: %s", filename, exc)

    return jsonify(
        {
            "ok": True,
            "imported_count": len(imported_ids),
            "imported_ids": imported_ids,
            "duplicates": duplicates,
            "errors": errors,
        }
    )


@biketracker_bp.route("/biketracker/delete", methods=["POST"])
def biketracker_delete():
    payload = request.get_json(silent=True) or {}
    file_id = payload.get("file")
    if not file_id:
        return jsonify({"ok": False, "error": "Keine Datei angegeben."}), 400

    source = get_source()
    try:
        filename = source.delete(file_id)
    except BikeTrackerSourceError as exc:
        current_app.logger.error("Fehler beim Löschen der BikeTracker-Datei %s: %s", file_id, exc)
        return jsonify({"ok": False, "error": str(exc)}), 500

    try:
        _delete_import(file_id)
    except mysql.connector.Error as exc:
        current_app.logger.error("Importstatus für %s nicht entfernt: %s", filename, exc)

    current_app.logger.info("BikeTracker-Datei %s nach '%s' verschoben.", filename,
                            current_app.config["BIKETRACKER_DELETED_FOLDER_NAME"])
    return jsonify({"ok": True, "filename": filename})
