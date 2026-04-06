from datetime import datetime, timezone
from typing import Literal

from kaori.database import get_db


async def get_location() -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM weather_location WHERE id = 1")
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def set_location(latitude: float, longitude: float, name: str | None = None) -> dict:
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO weather_location (id, latitude, longitude, name, updated_at) "
            "VALUES (1, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(id) DO UPDATE SET "
            "latitude = excluded.latitude, longitude = excluded.longitude, "
            "name = excluded.name, updated_at = datetime('now')",
            (latitude, longitude, name),
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM weather_location WHERE id = 1")
        row = await cursor.fetchone()
        return dict(row)
    finally:
        await db.close()


async def get_cached(date_str: str, weather_type: str) -> dict | None:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM weather_cache WHERE date = ? AND weather_type = ?",
            (date_str, weather_type),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def is_cache_fresh(date_str: str, weather_type: str, max_age_minutes: int = 30) -> bool:
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT fetched_at FROM weather_cache WHERE date = ? AND weather_type = ?",
            (date_str, weather_type),
        )
        row = await cursor.fetchone()
        if not row or not row["fetched_at"]:
            return False
        fetched = datetime.strptime(row["fetched_at"], "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
        age = (datetime.now(timezone.utc) - fetched).total_seconds() / 60
        return age < max_age_minutes
    finally:
        await db.close()


async def save_cache(
    date_str: str,
    weather_type: str,
    *,
    temperature: float | None = None,
    feels_like: float | None = None,
    temp_high: float | None = None,
    temp_low: float | None = None,
    humidity: int | None = None,
    wind_speed: float | None = None,
    weather_code: int | None = None,
    condition: str | None = None,
    icon: str | None = None,
    precipitation: float | None = None,
    uv_index: float | None = None,
    sunrise: str | None = None,
    sunset: str | None = None,
    data_json: str | None = None,
) -> int:
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO weather_cache "
            "(date, weather_type, temperature, feels_like, temp_high, temp_low, "
            "humidity, wind_speed, weather_code, condition, icon, precipitation, "
            "uv_index, sunrise, sunset, data_json, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(date, weather_type) DO UPDATE SET "
            "temperature=excluded.temperature, feels_like=excluded.feels_like, "
            "temp_high=excluded.temp_high, temp_low=excluded.temp_low, "
            "humidity=excluded.humidity, wind_speed=excluded.wind_speed, "
            "weather_code=excluded.weather_code, condition=excluded.condition, "
            "icon=excluded.icon, precipitation=excluded.precipitation, "
            "uv_index=excluded.uv_index, sunrise=excluded.sunrise, "
            "sunset=excluded.sunset, data_json=excluded.data_json, "
            "fetched_at=datetime('now')",
            (
                date_str, weather_type, temperature, feels_like, temp_high, temp_low,
                humidity, wind_speed, weather_code, condition, icon, precipitation,
                uv_index, sunrise, sunset, data_json,
            ),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def list_history(limit: int = 30) -> list[dict]:
    """List recent weather cache entries (current type only), newest first."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM weather_cache WHERE weather_type = 'current' "
            "ORDER BY date DESC LIMIT ?",
            (limit,),
        )
        return [dict(row) for row in await cursor.fetchall()]
    finally:
        await db.close()
