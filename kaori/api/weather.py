from datetime import date

from fastapi import APIRouter, HTTPException, Query

from kaori.models.weather import WeatherLocationUpdate
from kaori.services import weather_service
from kaori.storage import weather_repo

router = APIRouter(prefix="/weather", tags=["weather"])


@router.get("/location")
async def get_location():
    location = await weather_service.get_location()
    if not location:
        return {"latitude": None, "longitude": None, "name": None}
    return {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "name": location.get("name"),
    }


@router.put("/location")
async def set_location(body: WeatherLocationUpdate):
    result = await weather_service.set_location(
        latitude=body.latitude,
        longitude=body.longitude,
        name=body.name,
    )
    return {
        "latitude": result["latitude"],
        "longitude": result["longitude"],
        "name": result.get("name"),
    }


@router.get("/history")
async def get_history(limit: int = Query(default=30)):
    rows = await weather_repo.list_history(limit)
    return rows


@router.get("")
async def get_weather(date: str = Query(default=None)):
    if date is None:
        date = __import__("datetime").date.today().isoformat()
    weather = await weather_service.get_weather_for_date(date)
    if weather is None:
        raise HTTPException(status_code=404, detail="No weather data available. Set location first via PUT /api/weather/location")
    return weather
