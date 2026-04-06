from pydantic import BaseModel


class WeatherLocation(BaseModel):
    latitude: float
    longitude: float
    name: str | None = None


class WeatherLocationUpdate(BaseModel):
    latitude: float
    longitude: float
    name: str | None = None


class WeatherData(BaseModel):
    date: str
    weather_type: str  # "current" or "forecast"
    temperature: float | None = None
    feels_like: float | None = None
    temp_high: float | None = None
    temp_low: float | None = None
    humidity: int | None = None
    wind_speed: float | None = None
    weather_code: int | None = None
    condition: str | None = None
    icon: str | None = None  # SF Symbol name
    precipitation: float | None = None
    uv_index: float | None = None
    sunrise: str | None = None
    sunset: str | None = None


class WeatherResponse(BaseModel):
    current: WeatherData | None = None
    forecast: WeatherData | None = None
    location: WeatherLocation | None = None
    is_live: bool = False
