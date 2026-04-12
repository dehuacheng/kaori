import logging
from datetime import date, timedelta

from kaori.llm import get_llm_backend, LLMError
from kaori.llm.prompts import build_daily_summary_prompt
from kaori.services import profile_service, weight_service, workout_service, portfolio_service
from kaori.storage import meal_repo, summary_repo, post_repo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Context builders
# ---------------------------------------------------------------------------

async def _build_daily_context(target_date: str | None = None) -> tuple[str, dict]:
    """Build context string for a single day. Returns (context, raw_data)."""
    day = target_date or date.today().isoformat()

    meals = await meal_repo.list_by_date(day)
    totals = await meal_repo.get_totals(day)
    streak = await meal_repo.get_logging_streak()
    trends = await weight_service.get_trends(limit=7)
    workouts = await workout_service.list_workouts(target_date=day)
    profile = await profile_service.get_profile()

    parts = []

    # Profile targets
    if profile.get("target_calories"):
        parts.append(
            f"Targets: {profile['target_calories']} kcal, "
            f"{profile.get('target_protein_g', '?')}g protein"
        )

    # Meals detail
    meal_types_logged = [m["meal_type"] for m in meals]
    parts.append(f"Meals logged today: {', '.join(meal_types_logged) if meal_types_logged else 'none'}")
    for m in meals:
        cal = m.get("calories") or 0
        prot = m.get("protein_g") or 0
        desc = m.get("description") or "(no description)"
        parts.append(f"  - {m['meal_type']}: {desc} ({cal} kcal, {prot:.0f}g protein)")

    parts.append(
        f"Today's totals: {int(totals['total_cal'])} kcal, "
        f"{totals['total_protein']:.0f}g protein, "
        f"{totals['total_carbs']:.0f}g carbs, "
        f"{totals['total_fat']:.0f}g fat"
    )

    # Weight
    if trends.get("latest") is not None:
        parts.append(f"Latest weight: {trends['latest']:.1f} kg")
        if trends.get("avg_7d"):
            parts.append(f"7-day avg: {trends['avg_7d']:.1f} kg")
        if trends.get("delta_week"):
            parts.append(f"Week delta: {trends['delta_week']:+.1f} kg")

    # Workouts
    if workouts:
        parts.append(f"Workouts today: {len(workouts)}")
        for w in workouts:
            dur = w.get("duration_minutes")
            cal = w.get("calories_burned")
            summary = w.get("summary") or w.get("activity_type", "workout")
            detail = f"  - {summary}"
            if dur:
                detail += f" ({int(dur)} min"
                if cal:
                    detail += f", {int(cal)} kcal"
                detail += ")"
            parts.append(detail)

    # Portfolio
    try:
        portfolio = await portfolio_service.get_portfolio_summary(day)
        if portfolio and portfolio.get("combined"):
            combined = portfolio["combined"]
            total_val = combined.get("total_value", 0)
            day_change = combined.get("day_change", 0)
            day_pct = combined.get("day_change_pct", 0)
            parts.append(f"Portfolio: ${total_val:,.0f} (day change: {day_change:+,.0f}, {day_pct:+.1f}%)")
            if portfolio.get("top_movers"):
                movers = portfolio["top_movers"][:3]
                mover_strs = [f"{m['ticker']} {m['change_pct']:+.1f}%" for m in movers]
                parts.append(f"  Top movers: {', '.join(mover_strs)}")
    except Exception:
        pass  # Portfolio data optional for summary

    # Photo descriptions from posts (meals already have descriptions from analysis)
    posts = await post_repo.list_by_date(day)
    post_photo_descs = [(p.get("content", ""), p.get("photo_description")) for p in posts if p.get("photo_description")]
    if post_photo_descs:
        parts.append("Post photos:")
        for content, desc in post_photo_descs:
            parts.append(f"  - [{content[:50]}] {desc}")

    # Streak
    parts.append(f"Meal logging streak: {streak} day{'s' if streak != 1 else ''}")

    raw_data = {
        "streak": streak,
        "meals_logged": len(meals),
        "workouts_logged": len(workouts),
        "totals": {
            "calories": int(totals["total_cal"]),
            "protein_g": round(totals["total_protein"], 1),
            "carbs_g": round(totals["total_carbs"], 1),
            "fat_g": round(totals["total_fat"], 1),
        },
    }

    return "\n".join(parts), raw_data


# ---------------------------------------------------------------------------
# Short notification summaries (existing)
# ---------------------------------------------------------------------------

async def get_daily_summary(language: str = "en") -> dict:
    """Generate a brief (~140 char) LLM summary for notification use."""
    today = date.today().isoformat()
    context, raw_data = await _build_daily_context(today)

    summary_text = None
    try:
        profile = await profile_service.get_profile()
        backend = get_llm_backend(mode=profile.get("llm_mode"))
        prompt = build_daily_summary_prompt(context, language)
        response = await backend.complete(prompt)
        summary_text = response.text.strip().strip('"').strip("'")
        if len(summary_text) > 200:
            summary_text = summary_text[:197] + "..."
    except (LLMError, Exception):
        logger.exception("Daily summary LLM generation failed")

    return {
        "date": today,
        "summary": summary_text,
        **raw_data,
    }


async def get_weekly_weight_summary() -> dict:
    """Compute weekly weight trend summary (no LLM needed)."""
    trends = await weight_service.get_trends(limit=30)
    weights = trends.get("weights_asc", [])

    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()
    this_week = [w for w in weights if w["date"] >= week_ago]

    if not this_week:
        return {"date": today.isoformat(), "summary": None}

    values = [w["weight_kg"] for w in this_week]
    avg = sum(values) / len(values)
    latest = values[-1]
    earliest = values[0]
    delta = latest - earliest

    sign = "+" if delta > 0 else ""
    summary = f"This week: {sign}{delta:.1f} kg, avg {avg:.1f} kg ({len(this_week)} entries)"

    return {"date": today.isoformat(), "summary": summary}


# ---------------------------------------------------------------------------
# Detailed summaries (for in-app display)
# ---------------------------------------------------------------------------

async def _run_agent_summary(message: str) -> tuple[str, str, str]:
    """Run agent chat and collect the text response.

    Returns (text, backend_name, model_name).
    """
    from kaori.services import agent_chat_service
    from kaori.llm.agent_backend import get_agent_backend, get_agent_default_model

    text_parts: list[str] = []
    async for event in agent_chat_service.chat(
        message=message,
        source="summary",
    ):
        if event.get("type") == "text":
            text_parts.append(event["text"])

    backend = get_agent_backend()
    backend_name = getattr(backend, "name", "anthropic")
    model_name = get_agent_default_model() or "claude-sonnet-4-6"

    return "".join(text_parts).strip(), backend_name, model_name


async def generate_daily_detail(language: str = "zh", target_date: str | None = None) -> dict:
    """Generate a detailed daily health report via agent chat and store it."""
    day = target_date or date.today().isoformat()

    message = (
        f"Hey! Check out what happened on {day} — look up meals, weight, workouts, "
        f"portfolio, everything. Then write a quick recap of the day. "
        "Respond in Chinese (中文).\n\n"
        "Keep it short (~100-150 words), use real numbers with **bold** for the key ones. "
        "Use ## headers (营养 Nutrition, 运动 Activity, 体重 Weight, 建议 Tips) "
        "but skip any section with no data. "
        "Don't create a post — just give me the markdown."
    )

    summary_text, backend_name, model_name = await _run_agent_summary(message)

    stored = await summary_repo.create(
        summary_type="daily",
        target_date=day,
        summary_text=summary_text,
        llm_backend=backend_name,
        model=model_name,
        raw_response=summary_text,
    )

    return stored


async def generate_weekly_detail(language: str = "zh") -> dict:
    """Generate a detailed weekly health report via agent chat and store it."""
    today = date.today()
    target_date = today.isoformat()

    message = (
        f"Time for a weekly review! Look up the past 7 days (ending {target_date}) — "
        f"meals, weight, workouts, portfolio, all of it. "
        "Respond in Chinese (中文).\n\n"
        "Give me a ~200-300 word recap with **bold** key numbers. "
        "Use ## headers (体重趋势 Weight Trend, 营养 Nutrition, 训练 Training, "
        "投资组合 Portfolio, 计划 Plan) "
        "but skip any section with no data. End with 2-3 goals for next week. "
        "Don't create a post — just the markdown."
    )

    summary_text, backend_name, model_name = await _run_agent_summary(message)

    stored = await summary_repo.create(
        summary_type="weekly",
        target_date=target_date,
        summary_text=summary_text,
        llm_backend=backend_name,
        model=model_name,
        raw_response=summary_text,
    )

    return stored


async def get_daily_detail(target_date: str | None = None) -> dict | None:
    """Retrieve the latest stored daily detail for a date."""
    day = target_date or date.today().isoformat()
    return await summary_repo.get_latest("daily", day)


async def get_weekly_detail(target_date: str | None = None) -> dict | None:
    """Retrieve the latest stored weekly detail."""
    day = target_date or date.today().isoformat()
    return await summary_repo.get_latest("weekly", day)
