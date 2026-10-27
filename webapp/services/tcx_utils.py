import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from .gpx_utils import haversine

TCX_NS = "{http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2}"
TPX_NS = "{http://www.garmin.com/xmlschemas/ActivityExtension/v2}"

# Activity@Sport (Biking, Running, Other) auf activity_type abbilden
SPORT_TO_ACTIVITY_TYPE = {
    "biking": "cycling",
    "running": "running",
}


def _parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _float(element, path):
    found = element.find(path)
    if found is None or found.text is None:
        return None
    try:
        return float(found.text)
    except ValueError:
        return None


def _read_trackpoints(lap):
    points = []
    for tp in lap.iter(f"{TCX_NS}Trackpoint"):
        points.append({
            "time": _parse_time(tp.findtext(f"{TCX_NS}Time")),
            "lat": _float(tp, f"{TCX_NS}Position/{TCX_NS}LatitudeDegrees"),
            "lon": _float(tp, f"{TCX_NS}Position/{TCX_NS}LongitudeDegrees"),
            "altitude": _float(tp, f"{TCX_NS}AltitudeMeters"),
            "distance": _float(tp, f"{TCX_NS}DistanceMeters"),
            "cadence": _float(tp, f"{TCX_NS}Cadence"),
            "heart_rate": _float(tp, f"{TCX_NS}HeartRateBpm/{TCX_NS}Value"),
            "watts": _float(tp, f"{TCX_NS}Extensions/{TPX_NS}TPX/{TPX_NS}Watts"),
        })
    return points


def _load_activity(file_path: str):
    root = ET.parse(file_path).getroot()
    activity = root.find(f"{TCX_NS}Activities/{TCX_NS}Activity")
    if activity is None:
        raise ValueError("TCX enthält keine Aktivität")
    return activity


def _positive_ascent(altitudes):
    ascent = 0.0
    previous = None
    for altitude in altitudes:
        if previous is not None and altitude > previous:
            ascent += altitude - previous
        previous = altitude
    return ascent


def _weighted_lap_avg(laps, path):
    # Lap-Mittelwerte nach Lap-Dauer gewichten; 0 = kein Sensor
    total = weight = 0.0
    for lap in laps:
        value = _float(lap, path)
        duration = _float(lap, f"{TCX_NS}TotalTimeSeconds") or 0.0
        if value and duration:
            total += value * duration
            weight += duration
    return total / weight if weight else None


def _round_or_none(value, digits=None):
    if value is None:
        return None
    return round(value, digits) if digits is not None else int(round(value))


def parse_tcx(file_path: str) -> dict:
    activity = _load_activity(file_path)

    laps = activity.findall(f"{TCX_NS}Lap")
    if not laps:
        raise ValueError("TCX enthält keine Runden")

    points = [p for lap in laps for p in _read_trackpoints(lap)]
    if not points:
        raise ValueError("TCX enthält keine Trackpunkte")

    times = [p["time"] for p in points if p["time"]]
    if not times:
        raise ValueError("TCX enthält keine Zeitinformationen")

    start_time = min(times)
    end_time = max(times)

    # Strecke: Lap-Summen, sonst letzter Distanzwert, sonst aus den Koordinaten
    distance_m = sum(_float(lap, f"{TCX_NS}DistanceMeters") or 0.0 for lap in laps)
    if not distance_m:
        distance_m = max((p["distance"] for p in points if p["distance"] is not None), default=0.0)
    if not distance_m:
        positions = [p for p in points if p["lat"] is not None and p["lon"] is not None]
        distance_m = sum(
            haversine(a["lat"], a["lon"], b["lat"], b["lon"])
            for a, b in zip(positions, positions[1:])
        )

    altitudes = [p["altitude"] for p in points if p["altitude"] is not None]
    watts = [p["watts"] for p in points if p["watts"] is not None]
    cadences = [p["cadence"] for p in points if p["cadence"] is not None]
    heart_rates = [p["heart_rate"] for p in points if p["heart_rate"]]

    moving_time_s = sum(_float(lap, f"{TCX_NS}TotalTimeSeconds") or 0.0 for lap in laps)
    max_speed_ms = max((_float(lap, f"{TCX_NS}MaximumSpeed") or 0.0 for lap in laps), default=0.0)
    calories = sum(_float(lap, f"{TCX_NS}Calories") or 0.0 for lap in laps)

    avg_heart_rate = _weighted_lap_avg(laps, f"{TCX_NS}AverageHeartRateBpm/{TCX_NS}Value")
    if avg_heart_rate is None and heart_rates:
        avg_heart_rate = sum(heart_rates) / len(heart_rates)
    max_heart_rate = max(
        [_float(lap, f"{TCX_NS}MaximumHeartRateBpm/{TCX_NS}Value") or 0.0 for lap in laps] + heart_rates
    )

    activity_id = activity.findtext(f"{TCX_NS}Id") or start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Wie beim BikeTracker-GPX "Tour <Startzeit>", damit der Name nicht in tour_names landet
    name = (activity.findtext(f"{TCX_NS}Notes") or "").strip() or f"Tour {activity_id.strip()}"
    sport = (activity.get("Sport") or "").lower()
    device_name = (activity.findtext(f"{TCX_NS}Creator/{TCX_NS}Name") or "").strip() or None

    return {
        "activity_date": start_time.replace(tzinfo=None),
        "activity_name": name,
        "activity_type": SPORT_TO_ACTIVITY_TYPE.get(sport, "cycling"),
        "elapsed_time_s": int((end_time - start_time).total_seconds()),
        "distance_km": round(distance_m / 1000, 3),
        "elevation_gain_m": round(_positive_ascent(altitudes), 1),
        "min_elevation_m": round(min(altitudes), 1) if altitudes else None,
        "max_elevation_m": round(max(altitudes), 1) if altitudes else None,
        "avg_watts": _round_or_none(sum(watts) / len(watts)) if watts else None,
        "max_watts": _round_or_none(max(watts)) if watts else None,
        "calories": _round_or_none(calories) if calories else None,
        "moving_time_s": _round_or_none(moving_time_s) if moving_time_s else None,
        "max_speed_kmh": round(max_speed_ms * 3.6, 1) if max_speed_ms else None,
        "avg_cadence_rpm": _round_or_none(_weighted_lap_avg(laps, f"{TCX_NS}Cadence")),
        "max_cadence_rpm": _round_or_none(max(cadences)) if cadences and max(cadences) else None,
        "avg_heart_rate_bpm": _round_or_none(avg_heart_rate),
        "max_heart_rate_bpm": _round_or_none(max_heart_rate) if max_heart_rate else None,
        "device_name": device_name,
    }


def load_tcx_data(file_path: str):
    coords = []
    total_ascent_m = 0.0

    try:
        activity = _load_activity(file_path)
        points = [p for lap in activity.findall(f"{TCX_NS}Lap") for p in _read_trackpoints(lap)]

        for point in points:
            if point["lat"] is None or point["lon"] is None:
                continue
            # Fehlende Höhe bleibt leer, das Höhenprofil überspringt solche Punkte
            coords.append([point["lat"], point["lon"], point["altitude"]])

        total_ascent_m = _positive_ascent(p["altitude"] for p in points if p["altitude"] is not None)
    except Exception:
        pass

    return coords, total_ascent_m
