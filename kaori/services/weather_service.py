"""Weather service — fetches weather from Open-Meteo, caches results.

Today's weather is live (30-min cache TTL). Past dates return cached snapshots only.
"""

import json
import logging
from datetime import date, timedelta

import httpx

from kaori.storage import weather_repo

logger = logging.getLogger("kaori.weather")

# Cache TTL in minutes
_CURRENT_CACHE_TTL = 30
_FORECAST_CACHE_TTL = 120

# WMO Weather Code → (condition string, SF Symbol icon name)
_WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear", "sun.max.fill"),
    1: ("Mainly Clear", "sun.max.fill"),
    2: ("Partly Cloudy", "cloud.sun.fill"),
    3: ("Overcast", "cloud.fill"),
    45: ("Fog", "cloud.fog.fill"),
    48: ("Fog", "cloud.fog.fill"),
    51: ("Light Drizzle", "cloud.drizzle.fill"),
    53: ("Drizzle", "cloud.drizzle.fill"),
    55: ("Heavy Drizzle", "cloud.drizzle.fill"),
    56: ("Freezing Drizzle", "cloud.sleet.fill"),
    57: ("Freezing Drizzle", "cloud.sleet.fill"),
    61: ("Light Rain", "cloud.rain.fill"),
    63: ("Rain", "cloud.rain.fill"),
    65: ("Heavy Rain", "cloud.heavyrain.fill"),
    66: ("Freezing Rain", "cloud.sleet.fill"),
    67: ("Freezing Rain", "cloud.sleet.fill"),
    71: ("Light Snow", "cloud.snow.fill"),
    73: ("Snow", "cloud.snow.fill"),
    75: ("Heavy Snow", "cloud.snow.fill"),
    77: ("Snow Grains", "cloud.snow.fill"),
    80: ("Light Showers", "cloud.rain.fill"),
    81: ("Showers", "cloud.heavyrain.fill"),
    82: ("Heavy Showers", "cloud.heavyrain.fill"),
    85: ("Snow Showers", "cloud.snow.fill"),
    86: ("Heavy Snow Showers", "cloud.snow.fill"),
    95: ("Thunderstorm", "cloud.bolt.fill"),
    96: ("Thunderstorm + Hail", "cloud.bolt.rain.fill"),
    99: ("Thunderstorm + Hail", "cloud.bolt.rain.fill"),
}


def _weather_code_to_condition(code: int | None) -> tuple[str, str]:
    """Map WMO weather code to (condition, SF Symbol icon)."""
    if code is None:
        return ("Unknown", "questionmark.circle")
    return _WMO_CODES.get(code, ("Unknown", "questionmark.circle"))


async def get_location() -> dict | None:
    return await weather_repo.get_location()


async def set_location(latitude: float, longitude: float, name: str | None = None) -> dict:
    return await weather_repo.set_location(latitude, longitude, name)


async def get_weather_for_date(date_str: str) -> dict | None:
    """Get weather for a date. Live for today (with caching), static for past dates."""
    location = await weather_repo.get_location()
    if not location:
        return None

    today = date.today().isoformat()
    is_today = date_str == today
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    if is_today:
        # Live: fetch if cache is stale
        current_fresh = await weather_repo.is_cache_fresh(
            date_str, "current", _CURRENT_CACHE_TTL
        )
        forecast_fresh = await weather_repo.is_cache_fresh(
            tomorrow, "forecast", _FORECAST_CACHE_TTL
        )

        if not current_fresh or not forecast_fresh:
            try:
                await _fetch_and_cache(
                    location["latitude"], location["longitude"], date_str
                )
            except Exception:
                logger.exception("Failed to fetch weather from Open-Meteo")

        current = await weather_repo.get_cached(date_str, "current")
        forecast = await weather_repo.get_cached(tomorrow, "forecast")

        return _build_response(
            current, forecast, location, is_live=True, current_date=date_str, forecast_date=tomorrow
        )
    else:
        # Past date: return cached only (static snapshot)
        next_day = (date.fromisoformat(date_str) + timedelta(days=1)).isoformat()
        current = await weather_repo.get_cached(date_str, "current")
        forecast = await weather_repo.get_cached(next_day, "forecast")

        if not current and not forecast:
            return None

        return _build_response(
            current, forecast, location, is_live=False, current_date=date_str, forecast_date=next_day
        )


def _build_response(
    current: dict | None,
    forecast: dict | None,
    location: dict,
    is_live: bool,
    current_date: str,
    forecast_date: str,
) -> dict:
    """Build the weather response dict."""
    current_data = None
    if current:
        current_data = {
            "date": current_date,
            "weather_type": "current",
            "temperature": current.get("temperature"),
            "feels_like": current.get("feels_like"),
            "temp_high": current.get("temp_high"),
            "temp_low": current.get("temp_low"),
            "humidity": current.get("humidity"),
            "wind_speed": current.get("wind_speed"),
            "weather_code": current.get("weather_code"),
            "condition": current.get("condition"),
            "icon": current.get("icon"),
            "precipitation": current.get("precipitation"),
            "uv_index": current.get("uv_index"),
            "sunrise": current.get("sunrise"),
            "sunset": current.get("sunset"),
        }

    forecast_data = None
    if forecast:
        forecast_data = {
            "date": forecast_date,
            "weather_type": "forecast",
            "temperature": forecast.get("temperature"),
            "feels_like": forecast.get("feels_like"),
            "temp_high": forecast.get("temp_high"),
            "temp_low": forecast.get("temp_low"),
            "humidity": forecast.get("humidity"),
            "wind_speed": forecast.get("wind_speed"),
            "weather_code": forecast.get("weather_code"),
            "condition": forecast.get("condition"),
            "icon": forecast.get("icon"),
            "precipitation": forecast.get("precipitation"),
            "uv_index": forecast.get("uv_index"),
            "sunrise": forecast.get("sunrise"),
            "sunset": forecast.get("sunset"),
        }

    return {
        "current": current_data,
        "forecast": forecast_data,
        "location": {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "name": location.get("name"),
        },
        "is_live": is_live,
    }


async def _fetch_and_cache(lat: float, lon: float, today_str: str) -> None:
    """Fetch weather from Open-Meteo and save to cache."""
    tomorrow_str = (date.fromisoformat(today_str) + timedelta(days=1)).isoformat()

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        f"weather_code,wind_speed_10m,uv_index"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        f"sunrise,sunset,precipitation_sum"
        f"&timezone=auto&forecast_days=2"
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    logger.info("Open-Meteo response for (%.4f, %.4f): %d bytes", lat, lon, len(resp.text))

    # Parse current weather
    current = data.get("current", {})
    daily = data.get("daily", {})

    current_code = current.get("weather_code")
    condition, icon = _weather_code_to_condition(current_code)

    # Today's daily data (index 0)
    today_high = daily.get("temperature_2m_max", [None])[0]
    today_low = daily.get("temperature_2m_min", [None])[0]
    today_sunrise = daily.get("sunrise", [None])[0]
    today_sunset = daily.get("sunset", [None])[0]
    today_precip = daily.get("precipitation_sum", [None])[0]

    await weather_repo.save_cache(
        today_str, "current",
        temperature=current.get("temperature_2m"),
        feels_like=current.get("apparent_temperature"),
        temp_high=today_high,
        temp_low=today_low,
        humidity=current.get("relative_humidity_2m"),
        wind_speed=current.get("wind_speed_10m"),
        weather_code=current_code,
        condition=condition,
        icon=icon,
        precipitation=today_precip,
        uv_index=current.get("uv_index"),
        sunrise=today_sunrise,
        sunset=today_sunset,
        data_json=json.dumps({"current": current, "daily_today": {
            k: v[0] if isinstance(v, list) and v else v
            for k, v in daily.items()
        }}),
    )

    # Parse tomorrow's forecast (index 1)
    if len(daily.get("temperature_2m_max", [])) > 1:
        tmrw_code = daily.get("weather_code", [None, None])[1]
        tmrw_condition, tmrw_icon = _weather_code_to_condition(tmrw_code)

        await weather_repo.save_cache(
            tomorrow_str, "forecast",
            temp_high=daily.get("temperature_2m_max", [None, None])[1],
            temp_low=daily.get("temperature_2m_min", [None, None])[1],
            weather_code=tmrw_code,
            condition=tmrw_condition,
            icon=tmrw_icon,
            precipitation=daily.get("precipitation_sum", [None, None])[1],
            sunrise=daily.get("sunrise", [None, None])[1],
            sunset=daily.get("sunset", [None, None])[1],
            data_json=json.dumps({
                k: v[1] if isinstance(v, list) and len(v) > 1 else None
                for k, v in daily.items()
            }),
        )
