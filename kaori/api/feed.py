from datetime import date, timedelta

from fastapi import APIRouter, Query

from kaori.services import feed_service
from kaori.storage import card_preference_repo
from kaori.models.card import CardPreferenceUpdate

router = APIRouter(prefix="/feed", tags=["api-feed"])


@router.get("")
async def get_feed(
    start_date: str = Query(
        None,
        description="Start date (YYYY-MM-DD). Defaults to yesterday.",
    ),
    end_date: str = Query(
        None,
        description="End date (YYYY-MM-DD). Defaults to today.",
    ),
):
    """Get unified feed with all card types for a date range."""
    today = date.today()
    if not end_date:
        end_date = today.isoformat()
    if not start_date:
        start_date = (today - timedelta(days=1)).isoformat()
    return await feed_service.get_feed(start_date, end_date)


@router.get("/card-preferences")
async def get_card_preferences():
    """Get all card type preferences (enabled, pinned, order)."""
    return await feed_service.get_card_preferences()


@router.put("/card-preferences/{card_type}")
async def update_card_preference(card_type: str, body: CardPreferenceUpdate):
    """Update preference for a specific card type."""
    return await card_preference_repo.upsert(
        card_type,
        enabled=body.enabled,
        pinned=body.pinned,
        pin_order=body.pin_order,
    )
