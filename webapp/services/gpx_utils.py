import math
from datetime import timezone

import gpxpy
import gpxpy.gpx


def haversine(lat1, lon1, lat2, lon2):
    radius_m = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_m * c


def _extension_float(gpx, local_name: str):
    # Wert aus <gpx><extensions> lesen, Namespace-Präfix (z. B. bt:) wird ignoriert
    for element in gpx.extensions:
        if element.tag.rsplit("}", 1)[-1] == local_name:
            try:
                return float(element.text)
            except (TypeError, ValueError):
                return None
    return None


def parse_gpx(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as file_handle:
        gpx = gpxpy.parse(file_handle)

    if not gpx.tracks:
        raise ValueError("GPX enthält keine Tracks")

    track = gpx.tracks[0]
    if not track.segments:
        raise ValueError("GPX enthält keine Segmente")

    segment = track.segments[0]
    if not segment.points:
        raise ValueError("GPX enthält keine Trackpunkte")

    name = track.name or "Unbenannte Tour"
    activity_type = track.type or "cycling"

    distance_m = 0.0
    elevation_gain = 0.0
    times = []

    last_point = None
    for point in segment.points:
        if point.time:
            times.append(point.time)

        if last_point is not None:
            distance_m += haversine(
                last_point.latitude,
                last_point.longitude,
                point.latitude,
                point.longitude,
            )

            if point.elevation is not None and last_point.elevation is not None:
                diff = point.elevation - last_point.elevation
                if diff > 0:
                    elevation_gain += diff

        last_point = point

    if not times:
        raise ValueError("GPX enthält keine Zeitinformationen")

    start_time = min(times).astimezone(timezone.utc)
    end_time = max(times).astimezone(timezone.utc)
    duration_s = int((end_time - start_time).total_seconds())
    start_time_naive = start_time.replace(tzinfo=None)

    return {
        "activity_date": start_time_naive,
        "activity_name": name,
        "activity_type": activity_type,
        "elapsed_time_s": duration_s,
        "distance_km": round(distance_m / 1000, 3),
        "elevation_gain_m": round(elevation_gain, 1),
        "temp_min_c": _extension_float(gpx, "tempMin"),
        "temp_max_c": _extension_float(gpx, "tempMax"),
    }


def load_gpx_data(file_path: str):
    coords = []
    total_ascent_m = 0.0

    try:
        with open(file_path, "r", encoding="utf-8") as file_handle:
            gpx = gpxpy.parse(file_handle)

        for track in gpx.tracks:
            for segment in track.segments:
                previous_elevation = None

                for point in segment.points:
                    # Punkte ohne Höhe behalten (für den Track), Höhe aber leer lassen;
                    # das Höhenprofil überspringt sie, der Aufstieg zählt nur echte Höhen
                    elevation = point.elevation
                    coords.append([point.latitude, point.longitude, elevation])

                    if elevation is None:
                        continue

                    if previous_elevation is not None:
                        elevation_gain = elevation - previous_elevation
                        if elevation_gain > 0:
                            total_ascent_m += elevation_gain

                    previous_elevation = elevation
    except Exception:
        pass

    return coords, total_ascent_m


def parse_gpx_plan_tracks(content, fallback_name: str, activity: str) -> list:
    """Tracks (und Routen) einer externen GPX-Datei als Planungs-Tracks im Format des Arbeitsstands.

    Je GPX-Track bzw. -Route ein Eintrag {"name", "track"}; der Verlauf wird zu einem einzigen
    Segment zwischen Start- und Endpunkt zusammengefasst, damit er unverändert erhalten bleibt.
    """
    gpx = gpxpy.parse(content)

    # (Name, Punktlisten); Routen nur, wenn die Datei keine Tracks mit Punkten enthält
    sources = [
        (track.name, [seg.points for seg in track.segments])
        for track in gpx.tracks
        if any(seg.points for seg in track.segments)
    ]
    if not sources:
        sources = [(route.name, [route.points]) for route in gpx.routes if route.points]
    if not sources:
        raise ValueError("GPX enthält keine Tracks oder Routen mit Punkten")

    base_name = (gpx.name or "").strip() or fallback_name
    results = []
    for index, (name, point_lists) in enumerate(sources, start=1):
        coords = []
        distance_m = 0.0
        ascent_m = 0.0
        for points in point_lists:
            # Anstieg mit der Glättung von gpxpy, sonst treibt GPS-Rauschen den Wert nach oben
            part = gpxpy.gpx.GPXTrackSegment(points)
            distance_m += part.length_2d() or 0.0
            ascent_m += part.get_uphill_downhill().uphill or 0.0
            for point in points:
                coord = [round(point.latitude, 6), round(point.longitude, 6)]
                if point.elevation is not None:
                    coord.append(round(point.elevation, 1))
                if coords and coords[-1][:2] == coord[:2]:
                    continue
                coords.append(coord)

        track_name = (name or "").strip()
        if not track_name:
            track_name = base_name if len(sources) == 1 else f"{base_name} ({index})"

        start, end = coords[0][:2], coords[-1][:2]
        segments = []
        if len(coords) > 1:
            segments.append({
                "coords": coords,
                "distance_m": int(round(distance_m)),
                "ascent_m": int(round(ascent_m)),
                "activity": activity,
                "profile": "gpx-import",
                "routed": True,
                # Originalverlauf: die Planung routet beim Verschieben nur das Stück am Trackpunkt neu
                "imported": True,
            })
        results.append({
            "name": track_name[:255],
            "track": {
                "activity": activity,
                "points": [start, end] if segments else [start],
                "segments": segments,
            },
        })
    return results
