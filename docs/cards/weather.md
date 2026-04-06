# Card: Weather

## Identity
| Field | Value |
|-------|-------|
| Card Type | `weather` |
| CardType Enum | `CardType.WEATHER` |

## Purpose
Displays today's current weather conditions and tomorrow's forecast in the feed. Uses Open-Meteo API (free, no API key). Today's data is live (30-min cache TTL). Past dates show static snapshots of the weather that was recorded.

## Tables
| Table | Purpose |
|-------|---------|
| `weather_location` | Single-row table storing user's lat/lon/name |
| `weather_cache` | Cached weather data (current + forecast) per date |

## API Endpoints
- `GET /api/weather/location` — get stored location
- `PUT /api/weather/location` — set location `{ latitude, longitude, name }`
- `GET /api/weather?date=YYYY-MM-DD` — get weather for a specific date

## Feed Loader
`_load_weather` in `feed_service.py` — registered in `CARD_LOADERS`.

Populates `FeedDateGroup.weather` (dict) with:
- `current`: today's weather data (temperature, feels_like, high/low, condition, icon, etc.)
- `forecast`: tomorrow's forecast data (high/low, condition, precipitation)
- `location`: lat/lon/name
- `is_live`: true for today, false for past dates

## Key Files
- `kaori/models/weather.py` — Pydantic models
- `kaori/storage/weather_repo.py` — Location + cache CRUD
- `kaori/services/weather_service.py` — Open-Meteo fetch + caching + WMO code mapping
- `kaori/api/weather.py` — REST endpoints

## External API
Open-Meteo (`https://api.open-meteo.com/v1/forecast`) — free, no API key required.
WMO weather codes mapped to condition strings and SF Symbol icon names.
