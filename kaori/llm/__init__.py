from kaori.llm.base import LLMBackend, LLMError


def get_llm_backend(mode: str | None = None) -> LLMBackend:
    """Return the configured LLM backend instance."""
    if mode is None:
        from kaori.config import LLM_MODE
        mode = LLM_MODE
    if mode == "codex_cli":
        from kaori.llm.codex_cli import CodexCLIBackend
        return CodexCLIBackend()
    elif mode == "claude_api":
        from kaori.llm.claude_api import ClaudeAPIBackend
        return ClaudeAPIBackend()
    else:
        from kaori.llm.claude_cli import ClaudeCLIBackend
        return ClaudeCLIBackend()


__all__ = ["LLMBackend", "LLMError", "get_llm_backend"]
