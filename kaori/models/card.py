from enum import Enum

from pydantic import BaseModel


class CardType(str, Enum):
    MEAL = "meal"
    WEIGHT = "weight"
    WORKOUT = "workout"
    HEALTHKIT_WORKOUT = "healthkit_workout"
    PORTFOLIO = "portfolio"
    NUTRITION = "nutrition"
    SUMMARY = "summary"


class CardPreference(BaseModel):
    card_type: str
    enabled: bool = True
    pinned: bool = False
    pin_order: int = 99


class CardPreferenceUpdate(BaseModel):
    enabled: bool | None = None
    pinned: bool | None = None
    pin_order: int | None = None


class FeedItem(BaseModel):
    """A single item in the feed (meal, weight entry, workout, etc.)."""
    type: str
    id: int
    date: str
    created_at: str | None = None
    data: dict


class FeedDateGroup(BaseModel):
    """All feed data for a single date."""
    date: str
    items: list[FeedItem] = []
    nutrition_totals: dict | None = None
    summary: dict | None = None
    portfolio: dict | None = None


class FeedResponse(BaseModel):
    """Response from the unified feed endpoint."""
    dates: list[FeedDateGroup] = []
    card_preferences: list[CardPreference] = []
