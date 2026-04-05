"""Core agentic turn loop — ported from kaori-agent engine.py."""

from collections.abc import AsyncGenerator

from kaori.llm.agent_backend import (
    AgentLLMBackend, BaseTool, StreamEvent, ToolCall, ToolResult,
)


async def run_turn_stream(
    backend: AgentLLMBackend,
    messages: list,
    tools: list[BaseTool],
    system_prompt: str,
    model: str,
    max_tokens: int,
) -> AsyncGenerator[StreamEvent, None]:
    """Run one agentic turn with streaming. Yields StreamEvents.

    Handles the tool loop internally — yields thinking/text/tool_use events,
    executes tools, and loops until the model produces a final text response.
    Mutates `messages` in-place.
    """
    tool_schemas = backend.format_tool_schemas(tools) if tools else []
    tool_map = {t.name: t for t in tools}

    while True:
        turn_result = None
        async for event in backend.chat_stream(
            messages, tool_schemas, system_prompt, model, max_tokens,
        ):
            if event.type == "turn_complete":
                turn_result = event.result
            else:
                yield event

        if turn_result is None:
            return

        messages.append(backend.make_assistant_message(turn_result))

        if turn_result.stop_reason != "tool_use" or not turn_result.tool_calls:
            return

        # Execute tools and yield status events
        tool_results: list[ToolResult] = []
        for tc in turn_result.tool_calls:
            yield StreamEvent(type="tool_use", text=f"calling {tc.name}", tool_call=tc)
            tool = tool_map.get(tc.name)
            if tool is None:
                res = ToolResult(output=f"Unknown tool: {tc.name}", is_error=True)
            else:
                try:
                    res = await tool.execute(**tc.input)
                except Exception as e:
                    res = ToolResult(output=f"Tool execution error: {e}", is_error=True)
            tool_results.append(res)

        messages.extend(backend.make_tool_results(turn_result.tool_calls, tool_results))
