from fastapi import APIRouter, Query

from kaori.services import summary_service
from kaori.storage import meal_repo

router = APIRouter(prefix="/summary", tags=["api-summary"])


# ---------------------------------------------------------------------------
# Short notification summaries
# ---------------------------------------------------------------------------

@router.get("/daily")
async def daily_summary(language: str = Query("en", description="Language hint: en or zh")):
    return await summary_service.get_daily_summary(language=language)


@router.get("/weekly-weight")
async def weekly_weight_summary():
    return await summary_service.get_weekly_weight_summary()


@router.get("/streak")
async def meal_streak():
    streak = await meal_repo.get_logging_streak()
    return {"streak": streak}


# ---------------------------------------------------------------------------
# Detailed summaries (for in-app display)
# ---------------------------------------------------------------------------

@router.post("/daily-detail")
async def generate_daily_detail(
    language: str = Query("en"),
    date: str = Query(None, description="Date in YYYY-MM-DD format, defaults to today"),
):
    """Generate a new detailed daily report via LLM."""
    return await summary_service.generate_daily_detail(language=language, target_date=date)


@router.get("/daily-detail")
async def get_daily_detail(
    date: str = Query(None, description="Date in YYYY-MM-DD format, defaults to today"),
):
    """Retrieve the latest stored daily detail."""
    result = await summary_service.get_daily_detail(target_date=date)
    if result is None:
        return {"date": date, "summary_text": None}
    return result


@router.post("/weekly-detail")
async def generate_weekly_detail(language: str = Query("en")):
    """Generate a new detailed weekly report via LLM."""
    return await summary_service.generate_weekly_detail(language=language)


@router.get("/weekly-detail")
async def get_weekly_detail(
    date: str = Query(None, description="Date in YYYY-MM-DD format, defaults to today"),
):
    """Retrieve the latest stored weekly detail."""
    result = await summary_service.get_weekly_detail(target_date=date)
    if result is None:
        return {"date": date, "summary_text": None}
    return result
