import os
import shutil
from datetime import datetime

from flask import Blueprint, current_app, jsonify, render_template, request

from ..services.importer import process_gpx_file

biketracker_bp = Blueprint("biketracker", __name__)


def _list_latest_gpx_files(source_dir: str, max_files: int) -> list:
    entries = []
    with os.scandir(source_dir) as it:
        for entry in it:
            if entry.is_file() and entry.name.lower().endswith(".gpx"):
                stat = entry.stat()
                entries.append(
                    {
                        "name": entry.name,
                        "mtime": stat.st_mtime,
                        "date": datetime.fromtimestamp(stat.st_mtime).strftime("%d.%m.%Y %H:%M"),
                        "size_kb": stat.st_size / 1024,
                    }
                )

    entries.sort(key=lambda e: e["mtime"], reverse=True)
    return entries[:max_files]


@biketracker_bp.route("/biketracker", methods=["GET"])
def biketracker():
    source_dir = current_app.config["BIKETRACKER_DIR"]
    files = []
    error = None

    try:
        files = _list_latest_gpx_files(source_dir, current_app.config["BIKETRACKER_MAX_FILES"])
    except OSError as exc:
        current_app.logger.error("BikeTracker-Verzeichnis nicht lesbar (%s): %s", source_dir, exc)
        error = f"Verzeichnis {source_dir} ist nicht erreichbar."

    return render_template("biketracker.html", files=files, source_dir=source_dir, error=error)


@biketracker_bp.route("/biketracker/import", methods=["POST"])
def biketracker_import():
    payload = request.get_json(silent=True) or {}
    filenames = payload.get("files") or []
    if not filenames:
        return jsonify({"ok": False, "error": "Keine Dateien ausgewählt."}), 400

    source_dir = current_app.config["BIKETRACKER_DIR"]
    upload_tmp_dir = current_app.config["UPLOAD_TMP_DIR"]
    imported_ids = []
    errors = []

    for filename in filenames:
        # Nur reine Dateinamen aus dem BikeTracker-Verzeichnis zulassen
        if os.path.basename(filename) != filename or not filename.lower().endswith(".gpx"):
            errors.append({"filename": filename, "error": "Ungültiger Dateiname."})
            continue

        source_path = os.path.join(source_dir, filename)
        if not os.path.isfile(source_path):
            errors.append({"filename": filename, "error": "Datei nicht gefunden."})
            continue

        # Kopie importieren, da process_gpx_file die Quelldatei entfernt
        tmp_path = os.path.join(upload_tmp_dir, f"biketracker_{filename}")
        try:
            shutil.copy2(source_path, tmp_path)
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
