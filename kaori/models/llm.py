from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str
    backend: str
    usage: dict | None = None
