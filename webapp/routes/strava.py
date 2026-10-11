import os
import time
import requests
from flask import Blueprint, render_template, redirect, request, session, url_for, current_app, jsonify

strava_bp = Blueprint("strava", __name__)

STRAVA_AUTH_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_API_BASE = "https://www.strava.com/api/v3"

SESSION_KEYS = ("strava_access_token", "strava_refresh_token", "strava_token_expires_at")


def _get_client_id():
    return current_app.config.get("STRAVA_CLIENT_ID") or os.environ.get("STRAVA_CLIENT_ID")


def _get_client_secret():
    return current_app.config.get("STRAVA_CLIENT_SECRET") or os.environ.get("STRAVA_CLIENT_SECRET")


def _clear_tokens():
    """Entfernt alle Strava-Tokens aus der Session."""
    for key in SESSION_KEYS:
        session.pop(key, None)


def _store_tokens(data):
    session["strava_access_token"] = data["access_token"]
    session["strava_refresh_token"] = data["refresh_token"]
    session["strava_token_expires_at"] = data["expires_at"]


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
        current_app.logger.error(
            "Strava Token-Refresh Fehler %s: %s", resp.status_code, resp.text[:500]
        )
        _clear_tokens()
        return False

    _store_tokens(resp.json())
    return True


def _start_oauth():
    callback_url = url_for("strava.strava_callback", _external=True)
    auth_url = (
        f"{STRAVA_AUTH_URL}"
        f"?client_id={_get_client_id()}"
        f"&redirect_uri={callback_url}"
        f"&response_type=code"
        f"&scope=activity:read_all"
    )
    return redirect(auth_url)


def _error_page(message):
    return render_template("strava.html", error=message, activities=[])


@strava_bp.route("/strava")
def strava_index():
    """Einstiegspunkt: falls kein Token → OAuth starten, sonst Aktivitäten laden."""
    if not _refresh_token_if_needed():
        return _start_oauth()
    return _load_and_render_activities()


@strava_bp.route("/strava/reset")
def strava_reset():
    """Löscht gespeicherte Tokens und startet den OAuth-Flow neu."""
    _clear_tokens()
    return redirect(url_for("strava.strava_index"))


@strava_bp.route("/strava/callback")
def strava_callback():
    """OAuth Callback: Code gegen Token tauschen."""
    if request.args.get("error"):
        return _error_page("Zugriff auf Strava verweigert.")

    resp = requests.post(STRAVA_TOKEN_URL, data={
        "client_id": _get_client_id(),
        "client_secret": _get_client_secret(),
        "code": request.args.get("code"),
        "grant_type": "authorization_code",
    })

    if resp.status_code != 200:
        current_app.logger.error(
            "Strava Token-Austausch Fehler %s: %s", resp.status_code, resp.text[:500]
        )
        return _error_page(f"Token-Austausch fehlgeschlagen (HTTP {resp.status_code}).")

    _store_tokens(resp.json())
    return redirect(url_for("strava.strava_index"))


def _get_initial_row_count():
    """Liest strava.initial_row_count aus appsettings. Fallback: 5."""
    import mysql.connector
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


def _format_activity(a):
    """Wandelt eine Strava-Aktivität in das Anzeigeformat um."""
    dist_m = a.get("distance", 0)
    dist_km = round(dist_m / 1000, 2) if dist_m else 0

    elapsed_s = a.get("elapsed_time", 0)
    hours = elapsed_s // 3600
    minutes = (elapsed_s % 3600) // 60

    return {
        "strava_id": a.get("id"),
        "name": a.get("name", "–"),
        "sport_type": a.get("sport_type", a.get("type", "–")),
        "date": a.get("start_date_local", "")[:10],
        "distance_km": dist_km,
        "duration": f"{hours}:{minutes:02d} h",
    }


def _load_and_render_activities():
    """Lädt die letzten N Aktivitäten von Strava und rendert die Seite."""
    token = session["strava_access_token"]
    row_count = _get_initial_row_count()

    try:
        resp = requests.get(
            f"{STRAVA_API_BASE}/athlete/activities",
            headers={"Authorization": f"Bearer {token}"},
            params={"per_page": row_count, "page": 1},
            timeout=15,
        )
    except requests.RequestException as exc:
        current_app.logger.error("Strava activities Netzwerkfehler: %s", exc)
        return _error_page(f"Strava nicht erreichbar: {exc}")

    if resp.status_code != 200:
        current_app.logger.error(
            "Strava activities Fehler %s: %s", resp.status_code, resp.text[:500]
        )
        if resp.status_code == 401:
            _clear_tokens()
        return _error_page(
            f"Fehler beim Abrufen der Aktivitäten (HTTP {resp.status_code}). Details im Server-Log."
        )

    activities = [_format_activity(a) for a in resp.json()]
    return render_template("strava.html", activities=activities, error=None)


@strava_bp.route("/strava/import", methods=["POST"])
def strava_import():
    """Übernimmt ausgewählte Strava-Aktivitäten in die lokale Datenbank."""
    from ..services.importer import insert_strava_activity, save_strava_gpx

    if not _refresh_token_if_needed():
        return jsonify({"ok": False, "error": "Nicht authentifiziert."}), 401

    strava_ids = request.json.get("strava_ids", [])
    if not strava_ids:
        return jsonify({"ok": False, "error": "Keine Aktivitäten ausgewählt."}), 400

    token = session["strava_access_token"]
    imported = []
    duplicates = []
    errors = []

    for strava_id in strava_ids:
        try:
            resp = requests.get(
                f"{STRAVA_API_BASE}/activities/{strava_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code != 200:
                errors.append({"strava_id": strava_id, "error": f"API-Fehler {resp.status_code}"})
                continue

            activity_data = resp.json()
            activity_id = insert_strava_activity(activity_data)

            streams_resp = requests.get(
                f"{STRAVA_API_BASE}/activities/{strava_id}/streams",
                headers={"Authorization": f"Bearer {token}"},
                params={"keys": "latlng,altitude", "key_by_type": "true"},
            )
            current_app.logger.info("Streams Status: %s", streams_resp.status_code)
            if streams_resp.status_code == 200:
                save_strava_gpx(activity_id, activity_data, streams_resp.json())
            else:
                current_app.logger.warning(
                    "Keine GPS-Streams fuer Aktivitaet %s (Status %s): %s",
                    strava_id, streams_resp.status_code, streams_resp.text
                )

            imported.append({"strava_id": strava_id, "activity_id": activity_id})

        except ValueError as e:
            duplicates.append({"strava_id": strava_id, "error": str(e)})
        except Exception as e:
            current_app.logger.error("Strava-Import Fehler %s: %s", strava_id, e)
            errors.append({"strava_id": strava_id, "error": str(e)})

    return jsonify({
        "ok": True,
        "imported_count": len(imported),
        "imported": imported,
        "duplicates": duplicates,
        "errors": errors,
    })