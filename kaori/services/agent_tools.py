"""Server-side agent tools — call kaori services directly (no HTTP round-trip).

These are the tools the agent LLM can invoke during a chat turn.
They mirror the MCP server's read-only tools but call services directly.
"""

import json
from datetime import date, timedelta

from kaori.llm.agent_backend import BaseTool, ToolResult
from kaori.services import agent_service


def _format(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Domain tools (read-only, matching MCP server surface)
# ---------------------------------------------------------------------------

class GetFeedTool(BaseTool):
    name = "get_feed"
    description = (
        "Get the unified daily feed — meals, weight, workouts, portfolio, "
        "summaries, reminders, posts for a date range."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "start_date": {"type": "string", "description": "Start date YYYY-MM-DD. Defaults to yesterday."},
            "end_date": {"type": "string", "description": "End date YYYY-MM-DD. Defaults to today."},
        },
    }

    async def execute(self, start_date: str = "", end_date: str = "", **kw) -> ToolResult:
        from kaori.services import feed_service
        sd = start_date or (date.today() - timedelta(days=1)).isoformat()
        ed = end_date or date.today().isoformat()
        result = await feed_service.get_feed(sd, ed)
        return ToolResult(output=_format(result))


class GetMealsTool(BaseTool):
    name = "get_meals"
    description = "Get meals logged for a specific date, including nutrition totals."
    input_schema = {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Date YYYY-MM-DD. Defaults to today."},
        },
    }

    async def execute(self, date: str = "", **kw) -> ToolResult:
        from kaori.services import meal_service
        target = date or __import__("datetime").date.today().isoformat()
        result = await meal_service.list_by_date(target)
        return ToolResult(output=_format(result))


class GetWeightTool(BaseTool):
    name = "get_weight"
    description = "Get weight history and trends."
    input_schema = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Number of recent entries. Default 30."},
        },
    }

    async def execute(self, limit: int = 30, **kw) -> ToolResult:
        from kaori.services import weight_service
        result = await weight_service.get_history(limit=limit)
        return ToolResult(output=_format(result))


class GetProfileTool(BaseTool):
    name = "get_profile"
    description = "Get user profile — name, stats, nutrition targets, unit preferences."
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, **kw) -> ToolResult:
        from kaori.services import profile_service
        result = await profile_service.get_profile()
        return ToolResult(output=_format(result))


class GetPortfolioSummaryTool(BaseTool):
    name = "get_portfolio_summary"
    description = "Get investment portfolio summary — total value, daily change."
    input_schema = {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Date YYYY-MM-DD. Defaults to latest."},
        },
    }

    async def execute(self, date: str = "", **kw) -> ToolResult:
        from kaori.services import portfolio_service
        target = date or __import__("datetime").date.today().isoformat()
        result = await portfolio_service.get_portfolio_summary(target)
        return ToolResult(output=_format(result))


class GetWorkoutsTool(BaseTool):
    name = "get_workouts"
    description = "Get workout history — exercises, sets, duration."
    input_schema = {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Specific date YYYY-MM-DD."},
            "limit": {"type": "integer", "description": "Max entries. Default 30."},
        },
    }

    async def execute(self, date: str = "", limit: int = 30, **kw) -> ToolResult:
        from kaori.storage import workout_repo
        result = await workout_repo.list_workouts(
            date=date or None, limit=limit,
        )
        return ToolResult(output=_format(result))


class GetRemindersTool(BaseTool):
    name = "get_reminders"
    description = "Get reminders and to-do items."
    input_schema = {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Filter by due date YYYY-MM-DD."},
            "limit": {"type": "integer", "description": "Max entries. Default 50."},
        },
    }

    async def execute(self, date: str = "", limit: int = 50, **kw) -> ToolResult:
        from kaori.storage import reminder_repo
        if date:
            result = await reminder_repo.list_by_date(date)
        else:
            result = await reminder_repo.get_history(limit=limit)
        return ToolResult(output=_format(result))


class GetMealDetailTool(BaseTool):
    name = "get_meal_detail"
    description = "Get detailed information about a specific meal — nutrition breakdown, analysis."
    input_schema = {
        "type": "object",
        "properties": {
            "meal_id": {"type": "integer", "description": "The meal ID to look up."},
        },
        "required": ["meal_id"],
    }

    async def execute(self, meal_id: int, **kw) -> ToolResult:
        from kaori.services import meal_service
        result = await meal_service.get_by_id(meal_id)
        if not result:
            return ToolResult(output=f"Meal {meal_id} not found", is_error=True)
        return ToolResult(output=_format(result))


class GetWorkoutDetailTool(BaseTool):
    name = "get_workout_detail"
    description = "Get detailed workout info — all exercises with sets, reps, weights."
    input_schema = {
        "type": "object",
        "properties": {
            "workout_id": {"type": "integer", "description": "The workout ID to look up."},
        },
        "required": ["workout_id"],
    }

    async def execute(self, workout_id: int, **kw) -> ToolResult:
        from kaori.storage import workout_repo
        result = await workout_repo.get_workout(workout_id)
        if not result:
            return ToolResult(output=f"Workout {workout_id} not found", is_error=True)
        return ToolResult(output=_format(result))


class GetFinancialAccountsTool(BaseTool):
    name = "get_financial_accounts"
    description = "List all financial/brokerage accounts with their types and institutions."
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, **kw) -> ToolResult:
        from kaori.services import portfolio_service
        result = await portfolio_service.list_accounts()
        return ToolResult(output=_format(result))


class GetAccountHoldingsTool(BaseTool):
    name = "get_account_holdings"
    description = "Get holdings (stocks, ETFs, cash) in a specific financial account."
    input_schema = {
        "type": "object",
        "properties": {
            "account_id": {"type": "integer", "description": "The account ID to look up."},
        },
        "required": ["account_id"],
    }

    async def execute(self, account_id: int, **kw) -> ToolResult:
        from kaori.services import portfolio_service
        result = await portfolio_service.list_holdings(account_id)
        return ToolResult(output=_format(result))


class GetDailySummaryTool(BaseTool):
    name = "get_daily_summary"
    description = "Get the AI-generated daily health summary (meals, nutrition, weight, activity)."
    input_schema = {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Date YYYY-MM-DD. Defaults to today."},
        },
    }

    async def execute(self, date: str = "", **kw) -> ToolResult:
        from kaori.storage import summary_repo
        target = date or __import__("datetime").date.today().isoformat()
        result = await summary_repo.get_latest("daily", target)
        if not result:
            return ToolResult(output=f"No daily summary for {target}")
        return ToolResult(output=_format(result))


class GetWeeklySummaryTool(BaseTool):
    name = "get_weekly_summary"
    description = "Get the AI-generated weekly health summary (trends, patterns, recommendations)."
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, **kw) -> ToolResult:
        from kaori.services import summary_service
        result = await summary_service.get_weekly_detail()
        if not result:
            return ToolResult(output="No weekly summary available")
        return ToolResult(output=_format(result))


class GetMealStreakTool(BaseTool):
    name = "get_meal_streak"
    description = "Get the current meal logging streak (consecutive days with logged meals)."
    input_schema = {"type": "object", "properties": {}}

    async def execute(self, **kw) -> ToolResult:
        from kaori.storage import meal_repo
        streak = await meal_repo.get_logging_streak()
        return ToolResult(output=f"Current meal logging streak: {streak} days")


class GetExerciseTypesTool(BaseTool):
    name = "get_exercise_types"
    description = "List available exercise types for workout logging."
    input_schema = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Filter by category (chest, back, legs, etc.). Empty for all."},
        },
    }

    async def execute(self, category: str = "", **kw) -> ToolResult:
        from kaori.services import workout_service
        result = await workout_service.list_exercise_types(category=category or None)
        return ToolResult(output=_format(result))


# ---------------------------------------------------------------------------
# Document tools
# ---------------------------------------------------------------------------

class SearchDocumentsTool(BaseTool):
    name = "search_documents"
    description = (
        "Search uploaded documents (PDFs, screenshots) by keyword. "
        "Returns matching document summaries. Use get_document_detail for full text."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query. Empty to list all."},
        },
    }

    async def execute(self, query: str = "", **kw) -> ToolResult:
        from kaori.services import document_service
        if query:
            results = await document_service.search_documents(query)
        else:
            results = await document_service.list_documents()
        if not results:
            return ToolResult(output="No documents found.")
        return ToolResult(output=_format(results))


class GetDocumentDetailTool(BaseTool):
    name = "get_document_detail"
    description = "Get the full extracted text of a specific document by ID."
    input_schema = {
        "type": "object",
        "properties": {
            "document_id": {"type": "integer", "description": "The document ID."},
        },
        "required": ["document_id"],
    }

    async def execute(self, document_id: int, **kw) -> ToolResult:
        from kaori.services import document_service
        doc = await document_service.get_document(document_id)
        if not doc:
            return ToolResult(output=f"Document {document_id} not found", is_error=True)
        return ToolResult(output=_format(doc))


# ---------------------------------------------------------------------------
# Agent memory tools
# ---------------------------------------------------------------------------

class SaveMemoryTool(BaseTool):
    name = "save_memory"
    description = (
        "Save a fact or preference to persistent memory. "
        "Use this to remember things the user tells you."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Short key for the memory."},
            "value": {"type": "string", "description": "The value to remember."},
            "category": {
                "type": "string",
                "enum": ["general", "preference", "fact"],
                "description": "Category. Default: general.",
            },
        },
        "required": ["key", "value"],
    }

    def __init__(self, session_id: str | None = None):
        self._session_id = session_id

    async def execute(self, key: str, value: str, category: str = "general", **kw) -> ToolResult:
        entry = await agent_service.upsert_memory(
            key=key, value=value, category=category, source=self._session_id,
        )
        return ToolResult(output=f"Saved: {entry['key']} = {entry['value']}")


class GetMemoryTool(BaseTool):
    name = "get_memory"
    description = "Recall a specific memory by key, or list all memories."
    input_schema = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Key to look up. Omit for all."},
        },
    }

    async def execute(self, key: str = "", **kw) -> ToolResult:
        if key:
            entry = await agent_service.get_memory(key)
            if entry:
                return ToolResult(output=f"{entry['key']}: {entry['value']} [{entry['category']}]")
            return ToolResult(output=f"No memory found for key: {key}")
        entries = await agent_service.list_memory()
        if not entries:
            return ToolResult(output="No memories saved.")
        lines = [f"- {e['key']}: {e['value']} [{e['category']}]" for e in entries]
        return ToolResult(output="\n".join(lines))


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

def get_default_tools(session_id: str | None = None) -> list[BaseTool]:
    """Return all available agent tools."""
    return [
        GetFeedTool(),
        GetMealsTool(),
        GetMealDetailTool(),
        GetWeightTool(),
        GetProfileTool(),
        GetPortfolioSummaryTool(),
        GetFinancialAccountsTool(),
        GetAccountHoldingsTool(),
        GetWorkoutsTool(),
        GetWorkoutDetailTool(),
        GetRemindersTool(),
        GetDailySummaryTool(),
        GetWeeklySummaryTool(),
        GetMealStreakTool(),
        GetExerciseTypesTool(),
        SearchDocumentsTool(),
        GetDocumentDetailTool(),
        SaveMemoryTool(session_id=session_id),
        GetMemoryTool(),
    ]
