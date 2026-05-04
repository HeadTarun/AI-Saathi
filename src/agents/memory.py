from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver


class WorkflowMemory(ABC):
    """Checkpoint-backed memory interface for the study graph."""

    @abstractmethod
    def checkpointer(self) -> Any:
        """Return a LangGraph-compatible checkpointer."""

    @abstractmethod
    def thread_key(self, user_id: str, requested_thread_id: str | None = None) -> str:
        """Return the stable checkpoint thread key."""

    @abstractmethod
    def config(self, thread_key: str) -> dict[str, Any]:
        """Return LangGraph runnable config for the checkpoint thread."""

    @abstractmethod
    def load(self, thread_key: str) -> dict[str, Any]:
        """Load sanitized memory from the latest checkpoint."""


class LocalWorkflowMemory(WorkflowMemory):
    """In-process LangGraph checkpointer for local development and tests.

    A Postgres/Supabase implementation can keep this same interface and return an
    AsyncPostgresSaver/PostgresSaver from `checkpointer()`.
    """

    def __init__(self, saver: MemorySaver | None = None) -> None:
        self._saver = saver or MemorySaver()

    def checkpointer(self) -> MemorySaver:
        return self._saver

    def thread_key(self, user_id: str, requested_thread_id: str | None = None) -> str:
        suffix = requested_thread_id or "default"
        return f"study:{user_id}:{suffix}"

    def config(self, thread_key: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_key}}

    def load(self, thread_key: str) -> dict[str, Any]:
        checkpoint = self._saver.get(self.config(thread_key))
        values = (checkpoint or {}).get("channel_values") or {}
        metadata = values.get("metadata") or {}
        memory = metadata.get("memory") or {}
        return memory if isinstance(memory, dict) else {}


_DEFAULT_MEMORY = LocalWorkflowMemory()


def get_default_workflow_memory() -> WorkflowMemory:
    return _DEFAULT_MEMORY


def recent_messages_from_memory(memory: dict[str, Any]) -> list[BaseMessage]:
    messages = []
    for item in memory.get("recent_messages") or []:
        role = item.get("role")
        content = str(item.get("content") or "")
        if not content:
            continue
        if role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))
    return messages[-6:]


def sanitize_recent_messages(messages: list[BaseMessage], limit: int = 6) -> list[dict[str, str]]:
    sanitized = []
    for message in messages[-limit:]:
        role = "assistant" if getattr(message, "type", "") in {"ai", "assistant"} else "user"
        content = str(getattr(message, "content", "") or "")
        if content:
            sanitized.append({"role": role, "content": content[:1200]})
    return sanitized


__all__ = [
    "LocalWorkflowMemory",
    "WorkflowMemory",
    "get_default_workflow_memory",
    "recent_messages_from_memory",
    "sanitize_recent_messages",
]
