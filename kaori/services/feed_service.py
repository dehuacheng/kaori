"""Feed aggregation service — assembles unified feed from domain services.

New card types register a loader function in CARD_LOADERS. No hardcoded
if-blocks per card type — parallel development friendly.
"""

import logging
from datetime import date, timedelta
from typing import Callable, Awaitable

from kaori.models.card import CardType, FeedItem, FeedDateGroup, FeedResponse, CardPreference
from kaori.storage import card_preference_repo, meal_repo, weight_repo, summary_repo, post_repo
from kaori.services import meal_service, workout_service, portfolio_service, reminder_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Card loader registry — each card type registers a loader function.
# To add a new card type, just add an entry here. No other code in this file
# needs to change.
# ---------------------------------------------------------------------------

async def _load_meals(date_str: str, group: FeedDateGroup) -> None:
    meals = await meal_service.list_by_date(date_str)
    for m in meals:
        group.items.append(FeedItem(
            type=CardType.MEAL, id=m["id"], date=date_str,
            created_at=m.get("created_at"), data=m,
        ))


async def _load_nutrition(date_str: str, group: FeedDateGroup) -> None:
    totals = await meal_repo.get_totals(date_str)
    if totals and totals.get("total_cal", 0) > 0:
        group.nutrition_totals = totals


async def _load_weight(date_str: str, group: FeedDateGroup) -> None:
    weights = await weight_repo.list_by_date(date_str)
    for w in weights:
        group.items.append(FeedItem(
            type=CardType.WEIGHT, id=w["id"], date=date_str,
            created_at=w.get("created_at"), data=w,
        ))


async def _load_workouts(date_str: str, group: FeedDateGroup) -> None:
    workouts = await workout_service.list_workouts(target_date=date_str)
    for wo in workouts:
        source = wo.get("source", "manual")
        card_type = CardType.HEALTHKIT_WORKOUT if source == "healthkit" else CardType.WORKOUT
        group.items.append(FeedItem(
            type=card_type, id=wo["id"], date=date_str,
            created_at=wo.get("created_at"), data=wo,
        ))


async def _load_summary(date_str: str, group: FeedDateGroup) -> None:
    daily = await summary_repo.get_latest("daily", date_str)
    if daily:
        group.summary = daily


async def _load_portfolio(date_str: str, group: FeedDateGroup) -> None:
    portfolio = await portfolio_service.get_portfolio_summary(date_str)
    if portfolio and portfolio.get("combined"):
        group.portfolio = portfolio


async def _load_posts(date_str: str, group: FeedDateGroup) -> None:
    posts = await post_repo.list_by_date(date_str)
    for p in posts:
        group.items.append(FeedItem(
            type=CardType.POST, id=p["id"], date=date_str,
            created_at=p.get("created_at"), data=p,
        ))


async def _load_reminders(date_str: str, group: FeedDateGroup) -> None:
    items = await reminder_service.list_for_feed(date_str)
    for r in items:
        group.items.append(FeedItem(
            type=CardType.REMINDER, id=r["id"], date=date_str,
            created_at=r.get("created_at"), data=r,
        ))


# Registry: CardType → loader function
# To add a new card type, add ONE line here.
_CardLoader = Callable[[str, FeedDateGroup], Awaitable[None]]

CARD_LOADERS: dict[str, _CardLoader] = {
    CardType.MEAL: _load_meals,
    CardType.NUTRITION: _load_nutrition,
    CardType.WEIGHT: _load_weight,
    CardType.WORKOUT: _load_workouts,
    # HEALTHKIT_WORKOUT shares the same loader — dispatched by source field above
    CardType.SUMMARY: _load_summary,
    CardType.PORTFOLIO: _load_portfolio,
    CardType.POST: _load_posts,
    CardType.REMINDER: _load_reminders,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_card_preferences() -> list[CardPreference]:
    """Get all card preferences."""
    rows = await card_preference_repo.get_all()
    return [
        CardPreference(
            card_type=r["card_type"],
            enabled=bool(r["enabled"]),
            pinned=bool(r["pinned"]),
            pin_order=r["pin_order"],
        )
        for r in rows
    ]


def _is_card_enabled(prefs: list[CardPreference], card_type: str) -> bool:
    for p in prefs:
        if p.card_type == card_type:
            return p.enabled
    return True


async def get_feed(start_date: str, end_date: str) -> FeedResponse:
    """Aggregate all enabled card types for a date range."""
    prefs = await get_card_preferences()
    date_groups: list[FeedDateGroup] = []

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    current = end
    while current >= start:
        date_str = current.isoformat()
        group = await _build_date_group(date_str, prefs)
        date_groups.append(group)
        current -= timedelta(days=1)

    return FeedResponse(dates=date_groups, card_preferences=prefs)


async def _build_date_group(
    date_str: str, prefs: list[CardPreference]
) -> FeedDateGroup:
    """Build feed data for a single date by iterating registered loaders."""
    group = FeedDateGroup(date=date_str)

    for card_type, loader in CARD_LOADERS.items():
        if not _is_card_enabled(prefs, card_type):
            continue
        try:
            await loader(date_str, group)
        except Exception:
            logger.exception("Failed to load %s for %s", card_type, date_str)

    # Sort items by created_at descending
    group.items.sort(
        key=lambda x: x.created_at or "0000-00-00 00:00:00",
        reverse=True,
    )

    return group
