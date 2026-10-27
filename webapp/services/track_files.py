"""Einheitlicher Zugriff auf Tourdateien (GPX und TCX), Auswahl über die Dateiendung."""
import os

from .gpx_utils import load_gpx_data, parse_gpx
from .tcx_utils import load_tcx_data, parse_tcx

PARSERS = {
    ".gpx": parse_gpx,
    ".tcx": parse_tcx,
}

LOADERS = {
    ".gpx": load_gpx_data,
    ".tcx": load_tcx_data,
}

MIME_TYPES = {
    ".gpx": "application/gpx+xml",
    ".tcx": "application/vnd.garmin.tcx+xml",
}

SUPPORTED_EXTENSIONS = tuple(PARSERS)


def track_extension(filename: str) -> str:
    return os.path.splitext(filename or "")[1].lower()


def is_track_file(filename: str) -> bool:
    return track_extension(filename) in PARSERS


def parse_track_file(file_path: str, filename: str = None) -> dict:
    extension = track_extension(filename or file_path)
    parser = PARSERS.get(extension)
    if parser is None:
        raise ValueError(
            f"Dateiformat '{extension or '?'}' wird nicht unterstützt (erlaubt: {', '.join(SUPPORTED_EXTENSIONS)})"
        )
    return parser(file_path)


def load_track_data(file_path: str):
    loader = LOADERS.get(track_extension(file_path))
    if loader is None:
        return [], 0.0
    return loader(file_path)
