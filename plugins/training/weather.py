"""Weather tool for Hermes Coach.

Fetches current conditions and 48-hour forecast using the Open-Meteo API.
Open-Meteo is free, requires no API key, and covers global locations.

API docs: https://open-meteo.com/en/docs
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)

_API_BASE = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes → human-readable description
# https://open-meteo.com/en/docs#weathervariables
_WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def get_weather(
    latitude: float,
    longitude: float,
    location_name: Optional[str] = None,
    **_: Any,
) -> str:
    """Fetch current weather and 48-hour forecast for a lat/lon location.

    Returns temperature (°C), apparent temperature, precipitation,
    wind speed, wind direction, UV index, and weather description.

    Args:
        latitude:      Decimal latitude (e.g. 60.17 for Helsinki).
        longitude:     Decimal longitude (e.g. 24.94 for Helsinki).
        location_name: Optional display name included in the response.
    """
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "precipitation,wind_speed_10m,wind_direction_10m,"
            "weathercode,uv_index,is_day"
        ),
        "hourly": (
            "temperature_2m,apparent_temperature,precipitation_probability,"
            "precipitation,wind_speed_10m,weathercode,uv_index"
        ),
        "forecast_days": 2,
        "wind_speed_unit": "kmh",
        "timezone": "auto",
    }

    url = _API_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "hermes-coach/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return json.dumps({"error": f"Could not reach Open-Meteo: {exc.reason}"})

    current = data.get("current", {})
    hourly = data.get("hourly", {})
    timezone = data.get("timezone", "UTC")

    # Build a 24-hour summary (next 24 hours, 3-hour buckets)
    times = hourly.get("time", [])
    temp_h = hourly.get("temperature_2m", [])
    feel_h = hourly.get("apparent_temperature", [])
    precip_prob_h = hourly.get("precipitation_probability", [])
    precip_h = hourly.get("precipitation", [])
    wind_h = hourly.get("wind_speed_10m", [])
    code_h = hourly.get("weathercode", [])

    forecast_hours = []
    for i in range(0, min(24, len(times)), 3):
        forecast_hours.append({
            "time": times[i] if i < len(times) else None,
            "temp_c": temp_h[i] if i < len(temp_h) else None,
            "feels_like_c": feel_h[i] if i < len(feel_h) else None,
            "precip_prob_pct": precip_prob_h[i] if i < len(precip_prob_h) else None,
            "precip_mm": precip_h[i] if i < len(precip_h) else None,
            "wind_kmh": wind_h[i] if i < len(wind_h) else None,
            "conditions": _WMO_CODES.get(code_h[i] if i < len(code_h) else -1, "Unknown"),
        })

    wmo = current.get("weathercode", -1)
    result = {
        "source": "open-meteo.com",
        "location": location_name,
        "latitude": latitude,
        "longitude": longitude,
        "timezone": timezone,
        "current": {
            "temp_c": current.get("temperature_2m"),
            "feels_like_c": current.get("apparent_temperature"),
            "humidity_pct": current.get("relative_humidity_2m"),
            "precip_mm": current.get("precipitation"),
            "wind_kmh": current.get("wind_speed_10m"),
            "wind_direction_deg": current.get("wind_direction_10m"),
            "uv_index": current.get("uv_index"),
            "is_day": bool(current.get("is_day")),
            "conditions": _WMO_CODES.get(wmo, "Unknown"),
        },
        "forecast_24h": forecast_hours,
        "coaching_notes": _coaching_notes(current, forecast_hours),
    }
    return json.dumps(result)


def _coaching_notes(current: dict, forecast: list[dict]) -> list[str]:
    """Generate brief training-relevant weather observations."""
    notes = []
    temp = current.get("temperature_2m")
    feels = current.get("apparent_temperature")
    wind = current.get("wind_speed_10m", 0) or 0
    uv = current.get("uv_index", 0) or 0
    wmo = current.get("weathercode", 0) or 0

    if feels is not None and feels > 35:
        notes.append("Heat risk: apparent temperature above 35°C — avoid high intensity outdoors.")
    elif feels is not None and feels >= 30:
        notes.append(
            f"Hot conditions ({feels:.0f}°C feels-like). Train early or late in the day, "
            "reduce intensity 10–15%, and hydrate with electrolytes."
        )
    elif feels is not None and feels < -10:
        notes.append("Cold risk: apparent temperature below -10°C — dress in layers, reduce intensity.")
    elif feels is not None and feels <= 0:
        notes.append(
            f"Cold conditions ({feels:.0f}°C feels-like). Layer up, protect extremities "
            "(gloves, shoe covers), and warm up indoors first."
        )

    # Humidity amplifies heat stress at moderate temperatures
    humidity = current.get("relative_humidity_2m")
    if temp is not None and humidity is not None and temp >= 25 and humidity > 70 and not any(
        "Heat risk" in n for n in notes
    ):
        notes.append(
            f"Humid conditions ({humidity:.0f}% RH at {temp:.0f}°C) — "
            "sweat evaporation is reduced, raising effective heat stress. Increase fluid intake."
        )

    if wind > 50:
        notes.append(f"Strong wind ({wind:.0f} km/h) — expect significantly higher effort on exposed routes.")
    elif wind > 30:
        notes.append(f"Moderate wind ({wind:.0f} km/h) — plan route with wind direction in mind.")

    if uv > 8:
        notes.append(f"Very high UV index ({uv:.0f}) — apply sunscreen for rides over 30 minutes.")

    # Check rain in next 6h forecast
    rain_hours = [
        h for h in forecast[:2]
        if (h.get("precip_prob_pct") or 0) > 60 or (h.get("precip_mm") or 0) > 1
    ]
    if rain_hours:
        notes.append("Rain likely in the next 6 hours — consider indoor training or waterproof kit.")

    if wmo in {95, 96, 99}:
        notes.append("Thunderstorm active — do not train outdoors.")

    return notes


def register_tools(ctx) -> None:
    ctx.register_tool(
        name="get_weather",
        toolset="weather",
        schema={
            "name": "get_weather",
            "description": (
                "Fetch current weather conditions and 48-hour forecast for a location. "
                "Use this before recommending outdoor training to check temperature, "
                "wind, precipitation, and UV index. Returns coaching notes about "
                "conditions that affect training decisions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {
                        "type": "number",
                        "description": "Decimal latitude of the training location.",
                    },
                    "longitude": {
                        "type": "number",
                        "description": "Decimal longitude of the training location.",
                    },
                    "location_name": {
                        "type": "string",
                        "description": "Optional display name (e.g. 'Stockholm').",
                    },
                },
                "required": ["latitude", "longitude"],
            },
        },
        handler=lambda args, **kw: get_weather(
            latitude=float(args["latitude"]),
            longitude=float(args["longitude"]),
            location_name=args.get("location_name"),
        ),
    )
