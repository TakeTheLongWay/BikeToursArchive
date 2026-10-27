"""
Dateiquelle für die BikeTracker-Seite.

Zwei Varianten, umschaltbar über BIKETRACKER_SOURCE in config.py:
- "local": Verzeichnis im Dateisystem (z.B. gemountetes Google Drive G:)
- "drive": Google Drive API mit Dienstkonto

"Löschen" verschiebt eine Datei in den Unterordner BIKETRACKER_DELETED_FOLDER_NAME,
da das Dienstkonto Dateien des Drive-Eigentümers nicht in den Papierkorb legen darf.
"""
import io
import os
import shutil
from datetime import datetime, timezone

from flask import current_app

from .track_files import is_track_file

# Vollzugriff nötig, um Dateien in den Gelöscht-Ordner zu verschieben
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_FOLDER_MIME = "application/vnd.google-apps.folder"


class BikeTrackerSourceError(Exception):
    """Fehler beim Zugriff auf die BikeTracker-Quelle (wird auf der Seite angezeigt)."""


def _file_entry(file_id: str, name: str, modified: datetime, size_bytes: int) -> dict:
    return {
        "id": file_id,
        "name": name,
        "format": os.path.splitext(name)[1].lstrip(".").upper(),
        "mtime": modified,
        "date": modified.strftime("%d.%m.%Y %H:%M"),
        "size_kb": size_bytes / 1024,
    }


# ── Lokales Verzeichnis ──────────────────────────────────────────────────────

class LocalSource:
    def __init__(self, source_dir: str, deleted_folder_name: str):
        self.source_dir = source_dir
        self.deleted_folder_name = deleted_folder_name

    @property
    def label(self) -> str:
        return self.source_dir

    def list_latest_files(self, max_files: int) -> list:
        entries = []
        try:
            with os.scandir(self.source_dir) as it:
                for entry in it:
                    if entry.is_file() and is_track_file(entry.name):
                        stat = entry.stat()
                        modified = datetime.fromtimestamp(stat.st_mtime)
                        entries.append(_file_entry(entry.name, entry.name, modified, stat.st_size))
        except OSError as exc:
            raise BikeTrackerSourceError(f"Verzeichnis {self.source_dir} ist nicht erreichbar.") from exc

        entries.sort(key=lambda e: e["mtime"], reverse=True)
        return entries[:max_files]

    def _source_path(self, file_id: str) -> str:
        # Nur reine Dateinamen aus dem Verzeichnis zulassen
        if os.path.basename(file_id) != file_id or not is_track_file(file_id):
            raise BikeTrackerSourceError("Ungültiger Dateiname.")

        source_path = os.path.join(self.source_dir, file_id)
        if not os.path.isfile(source_path):
            raise BikeTrackerSourceError("Datei nicht gefunden.")
        return source_path

    def download(self, file_id: str, target_path: str) -> str:
        shutil.copy2(self._source_path(file_id), target_path)
        return file_id

    def delete(self, file_id: str) -> str:
        source_path = self._source_path(file_id)
        deleted_dir = os.path.join(self.source_dir, self.deleted_folder_name)
        try:
            os.makedirs(deleted_dir, exist_ok=True)
            # Vorhandene gleichnamige Datei im Gelöscht-Ordner wird überschrieben
            os.replace(source_path, os.path.join(deleted_dir, file_id))
        except OSError as exc:
            raise BikeTrackerSourceError(f"Datei konnte nicht verschoben werden: {exc}") from exc
        return file_id


# ── Google Drive API (Dienstkonto) ───────────────────────────────────────────

class DriveSource:
    def __init__(self, key_file: str, folder_id: str, folder_name: str, deleted_folder_name: str):
        self.key_file = key_file
        self.folder_id = folder_id
        self.folder_name = folder_name
        self.deleted_folder_name = deleted_folder_name
        self._service = None

    @property
    def label(self) -> str:
        return f"Google Drive: {self.folder_name}"

    def _get_service(self):
        if self._service is not None:
            return self._service

        if not os.path.isfile(self.key_file):
            raise BikeTrackerSourceError(f"Schlüsseldatei des Dienstkontos nicht gefunden: {self.key_file}")

        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        credentials = service_account.Credentials.from_service_account_file(self.key_file, scopes=DRIVE_SCOPES)
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return self._service

    def _execute(self, request):
        from googleapiclient.errors import HttpError

        try:
            return request.execute()
        except HttpError as exc:
            raise BikeTrackerSourceError(f"Google Drive meldet Fehler {exc.status_code}: {exc.reason}") from exc
        except OSError as exc:
            raise BikeTrackerSourceError(f"Google Drive nicht erreichbar: {exc}") from exc

    def _resolve_folder_id(self) -> str:
        if self.folder_id:
            return self.folder_id

        # Ordner über den Namen suchen; das Dienstkonto sieht nur freigegebene Ordner
        escaped_name = self.folder_name.replace("\\", "\\\\").replace("'", "\\'")
        result = self._execute(self._get_service().files().list(
            q=f"name = '{escaped_name}' and mimeType = '{DRIVE_FOLDER_MIME}' and trashed = false",
            fields="files(id, name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ))
        folders = result.get("files", [])

        if not folders:
            raise BikeTrackerSourceError(
                f"Ordner '{self.folder_name}' nicht gefunden. Ist er für das Dienstkonto freigegeben?"
            )
        if len(folders) > 1:
            raise BikeTrackerSourceError(
                f"Mehrere Ordner '{self.folder_name}' gefunden. Bitte BIKETRACKER_DRIVE_FOLDER_ID in config.py setzen."
            )

        self.folder_id = folders[0]["id"]
        return self.folder_id

    def list_latest_files(self, max_files: int) -> list:
        folder_id = self._resolve_folder_id()
        result = self._execute(self._get_service().files().list(
            q=f"'{folder_id}' in parents and trashed = false and mimeType != '{DRIVE_FOLDER_MIME}'",
            orderBy="modifiedTime desc",
            pageSize=100,
            fields="files(id, name, modifiedTime, size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ))

        entries = []
        for f in result.get("files", []):
            if not is_track_file(f["name"]):
                continue
            modified = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))
            modified = modified.astimezone().replace(tzinfo=None)
            entries.append(_file_entry(f["id"], f["name"], modified, int(f.get("size", 0))))
            if len(entries) >= max_files:
                break

        return entries

    def _get_file_meta(self, file_id: str) -> dict:
        folder_id = self._resolve_folder_id()

        # Nur GPX-/TCX-Dateien aus dem BikeTracker-Ordner zulassen
        meta = self._execute(self._get_service().files().get(
            fileId=file_id,
            fields="id, name, parents",
            supportsAllDrives=True,
        ))
        if folder_id not in meta.get("parents", []) or not is_track_file(meta["name"]):
            raise BikeTrackerSourceError("Datei gehört nicht zum BikeTracker-Ordner.")
        return meta

    def _get_deleted_folder_id(self) -> str:
        folder_id = self._resolve_folder_id()
        service = self._get_service()

        escaped_name = self.deleted_folder_name.replace("\\", "\\\\").replace("'", "\\'")
        result = self._execute(service.files().list(
            q=f"'{folder_id}' in parents and name = '{escaped_name}' "
              f"and mimeType = '{DRIVE_FOLDER_MIME}' and trashed = false",
            fields="files(id)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ))
        folders = result.get("files", [])
        if folders:
            return folders[0]["id"]

        created = self._execute(service.files().create(
            body={"name": self.deleted_folder_name, "mimeType": DRIVE_FOLDER_MIME, "parents": [folder_id]},
            fields="id",
            supportsAllDrives=True,
        ))
        return created["id"]

    def download(self, file_id: str, target_path: str) -> str:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaIoBaseDownload

        service = self._get_service()
        meta = self._get_file_meta(file_id)

        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, service.files().get_media(fileId=file_id, supportsAllDrives=True))
        done = False
        try:
            while not done:
                _, done = downloader.next_chunk()
        except HttpError as exc:
            raise BikeTrackerSourceError(f"Download fehlgeschlagen ({exc.status_code}): {exc.reason}") from exc

        with open(target_path, "wb") as fh:
            fh.write(buffer.getvalue())

        return meta["name"]

    def delete(self, file_id: str) -> str:
        meta = self._get_file_meta(file_id)
        self._execute(self._get_service().files().update(
            fileId=file_id,
            addParents=self._get_deleted_folder_id(),
            removeParents=self._resolve_folder_id(),
            fields="id",
            supportsAllDrives=True,
        ))
        return meta["name"]


def get_source():
    config = current_app.config
    if config["BIKETRACKER_SOURCE"] == "drive":
        return DriveSource(
            key_file=config["BIKETRACKER_DRIVE_KEY_FILE"],
            folder_id=config["BIKETRACKER_DRIVE_FOLDER_ID"],
            folder_name=config["BIKETRACKER_DRIVE_FOLDER_NAME"],
            deleted_folder_name=config["BIKETRACKER_DELETED_FOLDER_NAME"],
        )
    return LocalSource(config["BIKETRACKER_DIR"], config["BIKETRACKER_DELETED_FOLDER_NAME"])
