import os

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from ..services.importer import process_gpx_file

imports_bp = Blueprint("imports", __name__)


@imports_bp.route("/import", methods=["POST"])
def import_route():
    if "files" not in request.files:
        return jsonify({"ok": False, "error": "Keine Dateien gefunden."}), 400

    files = request.files.getlist("files")
    imported_ids = []
    errors = []

    upload_tmp_dir = current_app.config["UPLOAD_TMP_DIR"]

    for uploaded_file in files:
        if not uploaded_file.filename:
            continue

        filename = secure_filename(uploaded_file.filename)
        tmp_path = os.path.join(upload_tmp_dir, filename)

        try:
            uploaded_file.save(tmp_path)
            activity_id = process_gpx_file(tmp_path)
            imported_ids.append(activity_id)
        except Exception as exc:
            current_app.logger.error("Fehler beim Import von %s: %s", filename, exc)
            errors.append({"filename": filename, "error": str(exc)})

    return jsonify(
        {
            "ok": True,
            "imported_count": len(imported_ids),
            "imported_ids": imported_ids,
            "errors": errors,
        }
    )