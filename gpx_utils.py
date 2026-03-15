import math
from datetime import timezone

import gpxpy


def haversine(lat1, lon1, lat2, lon2):
    """
    Berechnet die Distanz zwischen zwei Koordinatenpunkten in Metern.
    """
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


def parse_gpx(file_path: str) -> dict:
    """
    Liest eine GPX-Datei und extrahiert Tourdaten für den Import.
    """
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
    }


def load_gpx_data(file_path: str):
    """
    Liest eine GPX-Datei für die Detailansicht und liefert:
    - coords: [[lat, lon, elevation], ...]
    - total_ascent_m: kumulierter positiver Höhengewinn
    """
    coords = []
    total_ascent_m = 0.0

    try:
        with open(file_path, "r", encoding="utf-8") as file_handle:
            gpx = gpxpy.parse(file_handle)

        for track in gpx.tracks:
            for segment in track.segments:
                previous_elevation = None

                for point in segment.points:
                    elevation = point.elevation if point.elevation is not None else 0.0
                    coords.append([point.latitude, point.longitude, elevation])

                    if previous_elevation is not None:
                        elevation_gain = elevation - previous_elevation
                        if elevation_gain > 0:
                            total_ascent_m += elevation_gain

                    previous_elevation = elevation
    except Exception:
        pass

    return coords, total_ascent_m