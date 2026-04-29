import os
import time
import requests
import mysql.connector
from flask import Blueprint, render_template, redirect, request, session, url_for, current_app

strava_bp = Blueprint("strava", __name__)

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"


def _get_client_id():
    return current_app.config.get("STRAVA_CLIENT_ID") or os.environ.get("STRAVA_CLIENT_ID")


def _get_client_secret():
    return current_app.config.get("STRAVA_CLIENT_SECRET") or os.environ.get("STRAVA_CLIENT_SECRET")


def _get_initial_row_count():
    """Liest strava.initial_row_count aus appsettings. Fallback: 5."""
    try:
        db_config = current_app.config["DB_CONFIG"]
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT setting_value FROM appsettings WHERE setting_key = %s",
            ("strava.initial_row_count",)
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row and row["setting_value"]:
            return int(row["setting_value"])
    except Exception as exc:
        current_app.logger.warning("strava.initial_row_count nicht lesbar: %s", exc)
    return 5


def _token_is_valid():
    """Prüft ob ein gültiger, noch nicht abgelaufener Token in der Session liegt."""
    token = session.get("strava_access_token")
    expires_at = session.get("strava_token_expires_at", 0)
    return token and time.time() < expires_at


def _refresh_token_if_needed():
    """Erneuert den Access Token automatisch über den Refresh Token."""
    if _token_is_valid():
        return True

    refresh_token = session.get("strava_refresh_token")
    if not refresh_token:
        return False

    resp = requests.post(STRAVA_TOKEN_URL, data={
        "client_id": _get_client_id(),
        "client_secret": _get_client_secret(),
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    })

    if resp.status_code != 200:
        return False

    data = resp.json()
    session["strava_access_token"] = data["access_token"]
    session["strava_refresh_token"] = data["refresh_token"]
    session["strava_token_expires_at"] = data["expires_at"]
    return True


@strava_bp.route("/strava")
def strava_index():
    """Einstiegspunkt: falls kein Token -> OAuth starten, sonst Aktivitaeten laden."""
    if not _refresh_token_if_needed():
        client_id = _get_client_id()
        callback_url = url_for("strava.strava_callback", _external=True)
        auth_url = (
            f"{STRAVA_AUTH_URL}"
            f"?client_id={client_id}"
            f"&redirect_uri={callback_url}"
            f"&response_type=code"
            f"&scope=activity:read_all"
        )
        return redirect(auth_url)

    return _load_and_render_activities()


@strava_bp.route("/strava/callback")
def strava_callback():
    """OAuth Callback: Code gegen Token tauschen."""
    error = request.args.get("error")
    if error:
        return render_template("strava.html", error="Zugriff auf Strava verweigert.", activities=[])

    code = request.args.get("code")
    resp = requests.post(STRAVA_TOKEN_URL, data={
        "client_id": _get_client_id(),
        "client_secret": _get_client_secret(),
        "code": code,
        "grant_type": "authorization_code",
    })

    if resp.status_code != 200:
        return render_template("strava.html", error="Token-Austausch fehlgeschlagen.", activities=[])

    data = resp.json()
    session["strava_access_token"] = data["access_token"]
    session["strava_refresh_token"] = data["refresh_token"]
    session["strava_token_expires_at"] = data["expires_at"]

    return redirect(url_for("strava.strava_index"))


def _load_and_render_activities():
    """Laedt die letzten N Aktivitaeten von Strava und rendert die Seite."""
    token = session["strava_access_token"]
    row_count = _get_initial_row_count()

    resp = requests.get(
        f"{STRAVA_API_BASE}/athlete/activities",
        headers={"Authorization": f"Bearer {token}"},
        params={"per_page": row_count, "page": 1},
    )

    if resp.status_code != 200:
        return render_template("strava.html", error="Fehler beim Abrufen der Aktivitaeten.", activities=[])

    raw = resp.json()
    activities = []
    for a in raw:
        dist_m = a.get("distance", 0)
        dist_km = round(dist_m / 1000, 2) if dist_m else 0

        elapsed_s = a.get("elapsed_time", 0)
        hours = elapsed_s // 3600
        minutes = (elapsed_s % 3600) // 60
        duration_str = f"{hours}:{minutes:02d} h"

        start_date = a.get("start_date_local", "")[:10]

        activities.append({
            "strava_id": a.get("id"),
            "name": a.get("name", "-"),
            "sport_type": a.get("sport_type", a.get("type", "-")),
            "date": start_date,
            "distance_km": dist_km,
            "duration": duration_str,
        })

    return render_template("strava.html", activities=activities, error=None, row_count=row_count)