from typing import Annotated, Any, Literal, Required, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


StudyIntent = Literal[
    "plan",
    "custom_plan",
    "teach",
    "quiz",
    "submit_quiz",
    "progress",
    "profile",
    "replan",
    "general",
    "clarify",
]

GraphStatus = Literal["pending", "running", "complete", "error"]


class ToolCallRecord(TypedDict, total=False):
    name: str
    args: dict[str, Any]
    id: str | None
    status: GraphStatus
    error: str | None


class StudyAgentState(TypedDict):
    """Shared state for the production LangGraph study workflow."""

    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    thread_id: str
    request_id: str
    user_query: str
    intent: StudyIntent
    status: GraphStatus
    auth: dict[str, Any]
    profile: dict[str, Any] | None
    active_plan: dict[str, Any] | None
    plan_day: dict[str, Any] | None
    topic: dict[str, Any] | None
    retrieved_context: list[dict[str, Any]]
    tool_calls: list[ToolCallRecord]
    tool_results: list[dict[str, Any]]
    structured_output: dict[str, Any] | None
    final: dict[str, Any] | None
    errors: list[dict[str, Any]]
    retry_count: int
    metadata: dict[str, Any]


class StudyAgentInput(TypedDict, total=False):
    user_id: Required[str]
    message: Required[str]
    thread_id: str
    request_id: str
    context: dict[str, Any]


class StudyAgentOutput(TypedDict):
    intent: StudyIntent
    status: GraphStatus
    answer: str
    data: dict[str, Any]
    errors: list[dict[str, Any]]
    thread_id: str
    request_id: str
