import asyncio
import json
import logging
import shutil

from kaori.llm.base import LLMBackend, LLMError
from kaori.models.llm import LLMResponse

logger = logging.getLogger(__name__)


class CodexCLIBackend(LLMBackend):
    """LLM backend using OpenAI Codex CLI as subprocess."""

    async def _run(self, prompt: str, *, image_path: str | None = None) -> LLMResponse:
        codex_path = shutil.which("codex")
        if not codex_path:
            raise LLMError("codex CLI not found in PATH")

        cmd = [
            codex_path, "exec",
            "--json",
            "--ephemeral",
            "--skip-git-repo-check",
        ]
        if image_path:
            cmd.extend(["-i", image_path, "-"])
        else:
            cmd.append(prompt)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if image_path else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdin_data = prompt.encode() if image_path else None
        stdout, stderr = await proc.communicate(input=stdin_data)

        if proc.returncode != 0:
            # Try to extract error from NDJSON output before falling back to stderr
            error_msg = _extract_error(stdout.decode()) or stderr.decode().strip()
            logger.error("codex CLI failed (rc=%d): %s", proc.returncode, error_msg)
            raise LLMError(f"codex CLI error: {error_msg}")

        text, usage = _parse_ndjson(stdout.decode())
        return LLMResponse(
            text=text,
            model="codex",
            backend="codex_cli",
            usage=usage,
        )

    async def complete(self, prompt: str, *, model: str = "sonnet") -> LLMResponse:
        return await self._run(prompt)

    async def analyze_image(self, image_path: str, prompt: str, *, model: str = "sonnet") -> LLMResponse:
        return await self._run(prompt, image_path=image_path)


def _parse_ndjson(output: str) -> tuple[str, dict | None]:
    """Parse NDJSON event stream from codex exec --json.

    Returns (text, usage) from the item.completed and turn.completed events.
    """
    text = ""
    usage = None
    for line in output.strip().splitlines():
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "item.completed":
            text = event.get("item", {}).get("text", "")
        elif event.get("type") == "turn.completed":
            raw_usage = event.get("usage", {})
            if raw_usage:
                usage = {
                    "input_tokens": raw_usage.get("input_tokens", 0),
                    "output_tokens": raw_usage.get("output_tokens", 0),
                }
    if not text:
        raise LLMError(f"No response text in codex output: {output[:200]}")
    return text, usage


def _extract_error(output: str) -> str | None:
    """Extract error message from NDJSON output, if present."""
    for line in output.strip().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "error":
            return event.get("message", "Unknown error")
        if event.get("type") == "turn.failed":
            return event.get("error", {}).get("message", "Unknown error")
    return None
