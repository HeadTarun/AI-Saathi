from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel


DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class LLMConfigurationError(RuntimeError):
    """Raised when no supported production LLM provider is configured."""


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def default_model_name() -> str:
    """Return the configured default chat model name."""
    load_dotenv()
    return _env("DEFAULT_MODEL") or DEFAULT_GROQ_MODEL


def configured_llm_provider() -> str:
    """Return the selected LLM provider name, or raise with setup guidance."""
    load_dotenv()
    if _env("GROQ_API_KEY"):
        return "groq"
    raise LLMConfigurationError(
        "No supported LLM API key configured. Set GROQ_API_KEY to enable the LangGraph "
        "study agent LLM runtime."
    )


@lru_cache(maxsize=4)
def get_llm(
    model: str | None = None,
    *,
    temperature: float = 0.0,
    max_retries: int = 2,
) -> BaseChatModel:
    """Initialize the configured chat model for LangGraph nodes.

    Groq is currently the only supported provider. The import is intentionally lazy so
    existing local-agent routes can start even when optional LLM dependencies are absent.
    """
    provider = configured_llm_provider()
    model_name = model or default_model_name()

    if provider == "groq":
        try:
            from langchain_groq import ChatGroq
        except ImportError as exc:
            raise LLMConfigurationError(
                "GROQ_API_KEY is configured, but langchain-groq is not installed. "
                "Install project dependencies before starting the LangGraph agent runtime."
            ) from exc
        return ChatGroq(model=model_name, temperature=temperature, max_retries=max_retries)

    raise LLMConfigurationError(f"Unsupported LLM provider: {provider}")
