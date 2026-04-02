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

    async def complete(self, prompt: str, *, model: str = "sonnet") -> LLMResponse:
        model_id = MODEL_MAP.get(model, model)
        try:
            response = await self._client.messages.create(
                model=model_id,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return LLMResponse(
                text=response.content[0].text,
                model=model,
                backend="claude_api",
                usage={"input_tokens": response.usage.input_tokens,
                       "output_tokens": response.usage.output_tokens},
            )
        except Exception as e:
            raise LLMError(f"Anthropic API error: {e}") from e

    async def analyze_image(self, image_data: bytes, prompt: str, *, media_type: str = "image/jpeg", model: str = "sonnet") -> LLMResponse:
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
            )
            return LLMResponse(
                text=response.content[0].text,
                model=model,
                backend="claude_api",
                usage={"input_tokens": response.usage.input_tokens,
                       "output_tokens": response.usage.output_tokens},
            )
        except Exception as e:
            raise LLMError(f"Anthropic API error: {e}") from e
