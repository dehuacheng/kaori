from abc import ABC, abstractmethod

from kaori.models.llm import LLMResponse


class LLMError(Exception):
    pass


class LLMBackend(ABC):
    """Abstract interface for LLM operations.

    Concrete implementations handle transport (CLI subprocess vs HTTP API).
    Callers only depend on this abstract class.
    """

    @abstractmethod
    async def complete(self, prompt: str, *, model: str = "sonnet") -> LLMResponse:
        ...

    @abstractmethod
    async def analyze_image(self, image_data: bytes, prompt: str, *, media_type: str = "image/jpeg", model: str = "sonnet") -> LLMResponse:
        ...
