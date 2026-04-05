"""Mock LLM backend for testing."""

from kaori.llm.base import LLMBackend
from kaori.models.llm import LLMResponse


class MockLLMBackend(LLMBackend):
    """Test double for LLMBackend that returns configurable responses."""

    def __init__(self, response_text: str = "{}"):
        self.response_text = response_text
        self.calls: list[tuple[str, str]] = []

    async def complete(self, prompt: str, *, model: str = "sonnet") -> LLMResponse:
        self.calls.append(("complete", prompt))
        return LLMResponse(text=self.response_text, model="mock", backend="mock")

    async def analyze_image(
        self, image_data: bytes, prompt: str, *,
        media_type: str = "image/jpeg", model: str = "sonnet", thinking: bool = True,
    ) -> LLMResponse:
        self.calls.append(("analyze_image", prompt))
        return LLMResponse(text=self.response_text, model="mock", backend="mock")

    async def analyze_images(
        self, images: list[tuple[bytes, str]], prompt: str, *,
        model: str = "sonnet", thinking: bool = True,
    ) -> LLMResponse:
        self.calls.append(("analyze_images", prompt))
        return LLMResponse(text=self.response_text, model="mock", backend="mock")

    async def analyze_document(
        self, document_data: bytes, prompt: str, *,
        media_type: str = "application/pdf", model: str = "sonnet", thinking: bool = True,
    ) -> LLMResponse:
        self.calls.append(("analyze_document", prompt))
        return LLMResponse(text=self.response_text, model="mock", backend="mock")
