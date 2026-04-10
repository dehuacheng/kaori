"""Kaori MCP Server — read-only tools for querying personal data.

Exposes Kaori's REST API as MCP tools for use by Claude Code,
kaori-agent, or any MCP-compatible client.

All tools are read-only (GET requests only). No data is modified.

Configuration via environment variables:
  KAORI_API_URL   — Base URL of the Kaori backend (default: http://localhost:8000)
  KAORI_API_TOKEN — Bearer token for authentication (default: dev-token)

Usage:
  python -m kaori.mcp_server
"""

import json
import os
from datetime import date, timedelta

import httpx
from mcp.server.fastmcp import FastMCP

# --- Config from env (no secrets in code) ---
API_URL = os.environ.get("KAORI_API_URL", "http://localhost:8000")
API_TOKEN = os.environ.get("KAORI_API_TOKEN", "dev-token")

mcp = FastMCP(
    "kaori",
    instructions=(
        "Kaori is a personal life management system. "
        "Use these tools to query and interact with the user's health, nutrition, "
        "fitness, finance, and daily planning data."
    ),
)

# --- HTTP helpers ---

def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {API_TOKEN}"}


def _get(path: str, params: dict | None = None) -> dict:
    """Make a GET request to the Kaori API."""
    url = f"{API_URL}{path}"
    resp = httpx.get(url, headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, json_body: dict) -> dict:
    """Make a POST request to the Kaori API."""
    url = f"{API_URL}{path}"
    resp = httpx.post(url, headers=_headers(), json=json_body, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _format(data: dict | list) -> str:
    """Format API response as readable JSON."""
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


# --- Tools ---

@mcp.tool()
def get_feed(start_date: str = "", end_date: str = "") -> str:
    """Get the unified daily feed — an overview of all logged data (meals, weight,
    workouts, portfolio, summaries, reminders, posts) for a date range.

    Args:
        start_date: Start date (YYYY-MM-DD). Defaults to yesterday.
        end_date: End date (YYYY-MM-DD). Defaults to today.
    """
    params = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return _format(_get("/api/feed", params))


@mcp.tool()
def get_meals(date: str = "") -> str:
    """Get meals logged for a specific date, including nutrition totals
    (calories, protein, carbs, fat).

    Args:
        date: Date to query (YYYY-MM-DD). Defaults to today.
    """
    params = {}
    if date:
        params["date"] = date
    return _format(_get("/api/meals", params))


@mcp.tool()
def get_meal_detail(meal_id: int) -> str:
    """Get detailed information about a specific meal, including
    individual food items and their nutrition breakdown.

    Args:
        meal_id: The meal ID to look up.
    """
    return _format(_get(f"/api/meals/{meal_id}"))


@mcp.tool()
def get_weight(limit: int = 30) -> str:
    """Get weight history and trends (recent entries, weekly/monthly averages,
    rate of change).

    Args:
        limit: Number of recent entries to return. Defaults to 30.
    """
    return _format(_get("/api/weight", {"limit": limit}))


@mcp.tool()
def get_profile() -> str:
    """Get the user's profile — display name, body stats, nutrition targets,
    unit preferences, and LLM settings."""
    return _format(_get("/api/profile"))


@mcp.tool()
def get_portfolio_summary(date: str = "") -> str:
    """Get investment portfolio summary — total value, holdings by account,
    daily change, and gain/loss.

    Args:
        date: Date for the snapshot (YYYY-MM-DD). Defaults to latest.
    """
    params = {}
    if date:
        params["date"] = date
    return _format(_get("/api/finance/portfolio/summary", params))


@mcp.tool()
def get_financial_accounts() -> str:
    """List all financial/brokerage accounts with their types and institutions."""
    return _format(_get("/api/finance/accounts"))


@mcp.tool()
def get_account_holdings(account_id: int) -> str:
    """Get holdings (stocks, ETFs, cash) in a specific financial account.

    Args:
        account_id: The account ID to look up.
    """
    return _format(_get(f"/api/finance/accounts/{account_id}/holdings"))


@mcp.tool()
def get_workouts(date: str = "", start_date: str = "", end_date: str = "", limit: int = 30) -> str:
    """Get workout history — exercises, sets, duration, and calories.

    Args:
        date: Specific date (YYYY-MM-DD). Takes precedence over range.
        start_date: Start of date range (YYYY-MM-DD).
        end_date: End of date range (YYYY-MM-DD).
        limit: Max entries to return. Defaults to 30.
    """
    params: dict = {"limit": limit}
    if date:
        params["date"] = date
    elif start_date:
        params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
    return _format(_get("/api/workouts", params))


@mcp.tool()
def get_workout_detail(workout_id: int) -> str:
    """Get detailed workout info — all exercises with sets, reps, weights.

    Args:
        workout_id: The workout ID to look up.
    """
    return _format(_get(f"/api/workouts/{workout_id}"))


@mcp.tool()
def get_daily_summary(date: str = "", language: str = "en") -> str:
    """Get the AI-generated daily health summary (meals, nutrition, weight, activity).

    Args:
        date: Date to query (YYYY-MM-DD). Defaults to today.
        language: Summary language — 'en' or 'zh'. Defaults to 'en'.
    """
    params: dict = {}
    if date:
        params["date"] = date
    data = _get("/api/summary/daily-detail", params)
    return _format(data)


@mcp.tool()
def get_weekly_summary(language: str = "en") -> str:
    """Get the AI-generated weekly health summary (trends, patterns, recommendations).

    Args:
        language: Summary language — 'en' or 'zh'. Defaults to 'en'.
    """
    return _format(_get("/api/summary/weekly-detail"))


@mcp.tool()
def get_reminders(date: str = "", limit: int = 50) -> str:
    """Get reminders and to-do items.

    Args:
        date: Filter by due date (YYYY-MM-DD). If empty, returns all recent.
        limit: Max entries to return. Defaults to 50.
    """
    params: dict = {"limit": limit}
    if date:
        params["date"] = date
    return _format(_get("/api/reminders", params))


@mcp.tool()
def get_meal_streak() -> str:
    """Get the current meal logging streak (consecutive days with logged meals)."""
    return _format(_get("/api/summary/streak"))


@mcp.tool()
def get_exercise_types(category: str = "") -> str:
    """List available exercise types for workout logging.

    Args:
        category: Filter by category (e.g., 'chest', 'back', 'legs'). Empty for all.
    """
    params: dict = {"enabled_only": "true"}
    if category:
        params["category"] = category
    return _format(_get("/api/exercise-types", params))


@mcp.tool()
def create_post(content: str, title: str = "", date: str = "") -> str:
    """Create a text post on the user's feed. Use this to write encouraging
    notes, observations, or summaries for the user.

    Args:
        content: The post content text (required).
        title: Optional short title for the post.
        date: Post date YYYY-MM-DD. Defaults to today.
    """
    body: dict = {"content": content}
    if title:
        body["title"] = title
    if date:
        body["date"] = date
    return _format(_post("/api/post/text", body))


@mcp.tool()
def get_sessions(limit: int = 20, status: str = "active") -> str:
    """List past agent conversation sessions — id, title, date, message count.

    Args:
        limit: Max sessions to return. Defaults to 20.
        status: Filter by status: 'active', 'archived', or empty string for all.
    """
    params: dict = {"limit": limit}
    if status:
        params["status"] = status
    return _format(_get("/api/agent/sessions", params))


@mcp.tool()
def get_session_messages(session_id: str) -> str:
    """Read messages from a specific past conversation session.

    Args:
        session_id: The session ID to read.
    """
    return _format(_get(f"/api/agent/sessions/{session_id}"))


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
