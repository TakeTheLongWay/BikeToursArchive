import os
import uuid

from flask import Blueprint, current_app, jsonify, render_template, request

from ..services.biketracker_source import BikeTrackerSourceError, get_source
from ..services.importer import process_gpx_file

biketracker_bp = Blueprint("biketracker", __name__)


@biketracker_bp.route("/biketracker", methods=["GET"])
def biketracker():
    source = get_source()
    files = []
    error = None

    try:
        files = source.list_latest_gpx(current_app.config["BIKETRACKER_MAX_FILES"])
    except BikeTrackerSourceError as exc:
        current_app.logger.error("BikeTracker-Quelle nicht lesbar (%s): %s", source.label, exc)
        error = str(exc)

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
    errors = []

    for file_id in file_ids:
        # Kopie importieren, da process_gpx_file die Quelldatei entfernt
        tmp_path = os.path.join(upload_tmp_dir, f"biketracker_{uuid.uuid4().hex}.gpx")
        filename = file_id
        try:
            filename = source.download(file_id, tmp_path)
            activity_id = process_gpx_file(tmp_path)
            imported_ids.append(activity_id)
        except Exception as exc:
            current_app.logger.error("Fehler beim BikeTracker-Import von %s: %s", filename, exc)
            errors.append({"filename": filename, "error": str(exc)})
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    return jsonify(
        {
            "ok": True,
            "imported_count": len(imported_ids),
            "imported_ids": imported_ids,
            "errors": errors,
        }
    )
