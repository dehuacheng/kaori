"""Heartbeat service — event-driven proactive agent triggers.

When the user logs a meal, weight, or post, this service is called
to optionally trigger the agent for a check-in. The agent reviews
recent data and may create an encouraging post on the feed.
"""

import logging
from datetime import datetime, timezone

from kaori.storage import heartbeat_repo

logger = logging.getLogger(__name__)

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
