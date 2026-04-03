import base64
import logging
import os

from kaori.llm.base import LLMBackend, LLMError
from kaori.models.llm import LLMResponse

logger = logging.getLogger(__name__)

MODEL_MAP = {
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
    "opus": "claude-opus-4-6",
}


def _thinking_param(thinking: bool) -> dict:
    """Build the thinking parameter for the Anthropic API."""
    if thinking:
        return {}  # default behavior (model decides)
    return {"thinking": {"type": "disabled"}}


class ClaudeAPIBackend(LLMBackend):
    """LLM backend using the Anthropic Python SDK."""

    def __init__(self):
        try:
            import anthropic
        except ImportError:
            raise LLMError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY environment variable not set")
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    def _build_response(self, response, model: str) -> LLMResponse:
        # Extract text from response, skipping thinking blocks
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break
        return LLMResponse(
            text=text,
            model=model,
            backend="claude_api",
            usage={"input_tokens": response.usage.input_tokens,
                   "output_tokens": response.usage.output_tokens},
        )

    async def complete(self, prompt: str, *, model: str = "sonnet") -> LLMResponse:
        model_id = MODEL_MAP.get(model, model)
        try:
            response = await self._client.messages.create(
                model=model_id,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._build_response(response, model)
        except Exception as e:
            raise LLMError(f"Anthropic API error: {e}") from e

    async def analyze_image(self, image_data: bytes, prompt: str, *, media_type: str = "image/jpeg", model: str = "sonnet", thinking: bool = True) -> LLMResponse:
        model_id = MODEL_MAP.get(model, model)
        b64 = base64.standard_b64encode(image_data).decode("utf-8")

        try:
            response = await self._client.messages.create(
                model=model_id,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                **_thinking_param(thinking),
            )
            return self._build_response(response, model)
        except Exception as e:
            raise LLMError(f"Anthropic API error (image): {e}") from e

    async def analyze_images(self, images: list[tuple[bytes, str]], prompt: str, *, model: str = "sonnet", thinking: bool = True) -> LLMResponse:
        import time
        model_id = MODEL_MAP.get(model, model)
        content = []
        total_bytes = 0
        for image_data, media_type in images:
            total_bytes += len(image_data)
            b64 = base64.standard_b64encode(image_data).decode("utf-8")
            content.append({"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}})
        content.append({"type": "text", "text": prompt})
        logger.info("analyze_images: %d images (%.0fKB total), model=%s, thinking=%s",
                     len(images), total_bytes / 1024, model_id, thinking)

        try:
            t0 = time.monotonic()
            response = await self._client.messages.create(
                model=model_id,
                max_tokens=4096,
                messages=[{"role": "user", "content": content}],
                **_thinking_param(thinking),
            )
            logger.info("analyze_images: API responded in %.1fs", time.monotonic() - t0)
            return self._build_response(response, model)
        except Exception as e:
            raise LLMError(f"Anthropic API error (images): {e}") from e

    async def analyze_document(self, document_data: bytes, prompt: str, *, media_type: str = "application/pdf", model: str = "sonnet", thinking: bool = True) -> LLMResponse:
        model_id = MODEL_MAP.get(model, model)
        b64 = base64.standard_b64encode(document_data).decode("utf-8")

        try:
            response = await self._client.messages.create(
                model=model_id,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "document", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                **_thinking_param(thinking),
            )
            return self._build_response(response, model)
        except Exception as e:
            raise LLMError(f"Anthropic API error (document): {e}") from e
