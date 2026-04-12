"""Heartbeat service — event-driven + scheduled proactive agent triggers.

Event-driven: when the user logs a meal, weight, or post, this service
optionally triggers the agent for a check-in.

Scheduled (nightly): at a configured time each day (default 21:00),
the agent reviews the day and creates a personal post about it.
"""

import logging
from datetime import date, datetime, timezone

from kaori.storage import heartbeat_repo

logger = logging.getLogger(__name__)

_DEFAULT_NIGHTLY_PROMPT = """\
You are Kaori, a warm and caring personal companion. It's the end of the day — time to reflect on what happened today and write a short, personal post about it.

Review the user's day using your tools:
1. Check today's feed (meals, weight, workouts, posts)
2. Look at their meal logging streak and recent weight trends
3. Check any posts they made today
4. Optionally check recent conversations for context

Write a short, personal post about their day. This is NOT a health summary or report — it's a diary-like reflection. Think of it as what a caring friend who was with them all day would write. Examples:
- Comment on interesting meals they had or a new restaurant they tried
- Note if they hit the gym or had a rest day
- React to any posts or photos they shared
- Mention small wins, patterns, or things that stood out
- Reference the weather, day of the week, or season if relevant

Keep it warm, personal, and conversational (3-5 sentences). Avoid bullet points and section headers — write it like a short diary entry or social media post. Use create_post with a fitting title and content.\
"""

_DEFAULT_PROMPT = """\
You are Kaori, a warm and caring personal wellness companion. You've just been notified that your user did something — check what happened and their recent data.

Review the user's recent activity using your tools:
1. Check today's feed (meals, weight, workouts, posts)
2. Look at their meal logging streak and recent weight trends
3. Optionally check their past sessions to recall recent conversations

Based on what you find, decide whether to create a short post on their feed. Good reasons to post:
- Celebrate a milestone (logging streak, weight goal, consistent workouts)
- React to what they just did (nice meal choice, getting back on track)
- Gentle encouragement if patterns suggest they need it
- A warm observation about their progress

If nothing particularly noteworthy stands out, respond with "No post needed." and do NOT create a post. Quality over quantity — only post when you have something genuinely meaningful to say.

When posting, keep it warm, concise (2-4 sentences), and personal. Use create_post with title and content.\
"""

# In-memory guard against concurrent heartbeat runs
_heartbeat_running = False


async def get_config() -> dict:
    return await heartbeat_repo.get_config()


async def update_config(**fields) -> dict:
    return await heartbeat_repo.update_config(**fields)


async def _should_run() -> bool:
    """Check if heartbeat is enabled and debounce period has elapsed."""
    config = await heartbeat_repo.get_config()
    if not config.get("enabled"):
        return False
    last_run = config.get("last_run_at")
    if not last_run:
        return True
    debounce = config.get("debounce_minutes", 5)
    try:
        last_dt = datetime.fromisoformat(last_run).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        elapsed_minutes = (now - last_dt).total_seconds() / 60
        return elapsed_minutes >= debounce
    except (ValueError, TypeError):
        return True


async def on_event(event_type: str, context: str = "") -> str | None:
    """Main entry point — called after user logs a meal/weight/post.

    Returns session_id if heartbeat ran, None if skipped.
    """
    global _heartbeat_running
    if _heartbeat_running:
        logger.debug("Heartbeat already running, skipping")
        return None

    if not await _should_run():
        logger.debug("Heartbeat skipped (disabled or debounce)")
        return None

    _heartbeat_running = True
    try:
        return await _run_heartbeat(event_type, context)
    except Exception:
        logger.exception("Heartbeat error")
        return None
    finally:
        _heartbeat_running = False


async def trigger_manual() -> str | None:
    """Manual trigger for testing — bypasses debounce check."""
    global _heartbeat_running
    if _heartbeat_running:
        return None

    config = await heartbeat_repo.get_config()
    if not config.get("enabled"):
        return None

    _heartbeat_running = True
    try:
        return await _run_heartbeat("manual", "Manual trigger")
    except Exception:
        logger.exception("Heartbeat manual trigger error")
        return None
    finally:
        _heartbeat_running = False


async def _run_heartbeat(event_type: str, context: str) -> str | None:
    """Execute a heartbeat: create session, run agent, record result."""
    from kaori.services import agent_chat_service

    config = await heartbeat_repo.get_config()
    prompt_template = config.get("prompt_template") or _DEFAULT_PROMPT

    # Build the trigger message
    message = f"[Heartbeat trigger: {event_type}]"
    if context:
        message += f" {context}"

    # Build system prompt with date/time context
    now = datetime.now()
    utc_now = datetime.now(timezone.utc)
    system_prompt = (
        f"{prompt_template}\n\n"
        f"Current date and time: {now.strftime('%Y-%m-%d %H:%M %A')} (local), "
        f"{utc_now.strftime('%Y-%m-%d %H:%M')} UTC\n\n"
        f"Trigger event: {event_type}"
    )

    # Run the agent chat with heartbeat overrides
    session_id = None
    async for event in agent_chat_service.chat(
        message=message,
        system_prompt_override=system_prompt,
        source="heartbeat",
        post_source="agent",
    ):
        if event.get("type") == "session":
            session_id = event.get("session_id")
        # Consume all events (agent does its thing)

    if session_id:
        await heartbeat_repo.record_run(session_id, event_type)
        logger.info("Heartbeat completed: session=%s event=%s", session_id, event_type)

    return session_id


# ---------------------------------------------------------------------------
# Scheduled nightly heartbeat
# ---------------------------------------------------------------------------

async def trigger_nightly_manual() -> str | None:
    """Manual nightly trigger for testing — bypasses schedule/date check."""
    global _heartbeat_running
    if _heartbeat_running:
        return None

    _heartbeat_running = True
    try:
        return await _run_nightly()
    except Exception:
        logger.exception("Nightly heartbeat manual trigger error")
        return None
    finally:
        _heartbeat_running = False


async def should_run_nightly() -> bool:
    """Check if nightly heartbeat should run (enabled + not yet run today)."""
    config = await heartbeat_repo.get_config()
    if not config.get("schedule_enabled"):
        return False
    today = date.today().isoformat()
    return config.get("last_nightly_date") != today


async def get_schedule_time() -> str:
    """Return the configured schedule time (HH:MM), default '21:00'."""
    config = await heartbeat_repo.get_config()
    return config.get("schedule_time") or "21:00"


async def trigger_nightly() -> str | None:
    """Nightly scheduled trigger — generates a personal post about the day.

    Returns session_id if the heartbeat ran, None if skipped.
    """
    global _heartbeat_running
    if _heartbeat_running:
        logger.debug("Heartbeat already running, skipping nightly")
        return None

    if not await should_run_nightly():
        return None

    _heartbeat_running = True
    try:
        return await _run_nightly()
    except Exception:
        logger.exception("Nightly heartbeat error")
        return None
    finally:
        _heartbeat_running = False


async def _run_nightly() -> str | None:
    """Execute the nightly heartbeat: create a personal post about the day."""
    from kaori.services import agent_chat_service, agent_service

    config = await heartbeat_repo.get_config()
    prompt_template = config.get("nightly_prompt_template") or _DEFAULT_NIGHTLY_PROMPT

    # Resolve personality and prepend it to the nightly prompt
    personality = await agent_service.get_personality_text()
    if personality:
        prompt_template = f"{personality}\n\n---\n\n{prompt_template}"

    now = datetime.now()
    utc_now = datetime.now(timezone.utc)
    system_prompt = (
        f"{prompt_template}\n\n"
        f"Current date and time: {now.strftime('%Y-%m-%d %H:%M %A')} (local), "
        f"{utc_now.strftime('%Y-%m-%d %H:%M')} UTC"
    )

    message = "[Nightly heartbeat] End-of-day reflection"

    session_id = None
    async for event in agent_chat_service.chat(
        message=message,
        system_prompt_override=system_prompt,
        source="heartbeat",
        post_source="agent",
    ):
        if event.get("type") == "session":
            session_id = event.get("session_id")

    if session_id:
        today = date.today().isoformat()
        await heartbeat_repo.record_nightly_run(session_id, today)
        logger.info("Nightly heartbeat completed: session=%s date=%s", session_id, today)

    return session_id
