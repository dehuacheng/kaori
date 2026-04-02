import asyncio
import json
import logging
import shutil

from kaori.llm.base import LLMBackend, LLMError
from kaori.models.llm import LLMResponse

logger = logging.getLogger(__name__)


class ClaudeCLIBackend(LLMBackend):
    """LLM backend using Claude Code CLI as subprocess."""

    async def _run(self, prompt: str, *, model: str = "sonnet", allowed_tools: str | None = None) -> LLMResponse:
        claude_path = shutil.which("claude")
        if not claude_path:
            raise LLMError("claude CLI not found in PATH")

        cmd = [
            claude_path, "-p",
            "--output-format", "json",
            "--no-session-persistence",
            "--model", model,
        ]
        if allowed_tools:
            cmd.extend(["--allowedTools", allowed_tools])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(input=prompt.encode())

        if proc.returncode != 0:
            err = stderr.decode().strip()
            logger.error("claude CLI failed (rc=%d): %s", proc.returncode, err)
            raise LLMError(f"claude CLI error: {err}")

        output = stdout.decode().strip()
        try:
            data = json.loads(output)
            if data.get("is_error"):
                raise LLMError(f"claude CLI error: {data.get('result', 'Unknown')}")
            return LLMResponse(
                text=data.get("result", output),
                model=model,
                backend="claude_cli",
            )
        except json.JSONDecodeError:
            return LLMResponse(text=output, model=model, backend="claude_cli")

    async def complete(self, prompt: str, *, model: str = "sonnet") -> LLMResponse:
        return await self._run(prompt, model=model)

    async def analyze_image(self, image_data: bytes, prompt: str, *, media_type: str = "image/jpeg", model: str = "sonnet") -> LLMResponse:
        import tempfile
        # Write resized image to a temp file for the CLI's Read tool
        suffix = ".jpg" if "jpeg" in media_type else f".{media_type.split('/')[-1]}"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name
        logger.debug("analyze_image (CLI): wrote %d bytes to %s", len(image_data), tmp_path)
        try:
            full_prompt = f"Read the image file at {tmp_path}. {prompt}"
            return await self._run(full_prompt, model=model, allowed_tools="Read")
        finally:
            import os
            os.unlink(tmp_path)
