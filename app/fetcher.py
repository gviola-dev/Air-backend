"""
Fetcha dati da due API pubbliche di Open-Meteo (zero API key richieste):
  1. Forecast  → temperatura, windspeed, weathercode
  2. Air Quality → PM10, European AQI

Coordinate: Napoli (lat=40.85, lon=14.27)
"""
import httpx
from sqlalchemy.orm import Session
from app import crud

LAT = 40.85
LON = 14.27

FORECAST_URL = (
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}&current_weather=true"
)

AIR_QUALITY_URL = (
    f"https://air-quality-api.open-meteo.com/v1/air-quality"
    f"?latitude={LAT}&longitude={LON}&current=pm10,european_aqi"
)


def fetch_and_store(db: Session) -> dict:
    results = {}
    with httpx.Client(timeout=10.0) as client:
        results["forecast"]    = _fetch_forecast(client, db)
        results["air_quality"] = _fetch_air_quality(client, db)
    return results


# ── private ──────────────────────────────────────────────────────────────────

def _fetch_forecast(client: httpx.Client, db: Session) -> str:
    try:
        r = client.get(FORECAST_URL)
        r.raise_for_status()
        cw = r.json()["current_weather"]
        crud.save_reading(
            db,
            source="forecast",
            latitude=LAT,
            longitude=LON,
            temperature=cw["temperature"],
            windspeed=cw["windspeed"],
            weathercode=int(cw["weathercode"]),
        )
        print(f"[fetcher] forecast OK — {cw['temperature']}°C, {cw['windspeed']} km/h")
        return "ok"
    except Exception as e:
        print(f"[fetcher] forecast ERROR: {e}")
        return str(e)


def _fetch_air_quality(client: httpx.Client, db: Session) -> str:
    try:
        r = client.get(AIR_QUALITY_URL)
        r.raise_for_status()
        current = r.json().get("current", {})
        crud.save_reading(
            db,
            source="air_quality",
            latitude=LAT,
            longitude=LON,
            pm10=current.get("pm10"),
            european_aqi=current.get("european_aqi"),
        )
        print(f"[fetcher] air_quality OK — PM10={current.get('pm10')}, AQI={current.get('european_aqi')}")
        return "ok"
    except Exception as e:
        print(f"[fetcher] air_quality ERROR: {e}")
        return str(e)
