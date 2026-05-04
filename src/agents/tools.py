from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

import study_core

try:
    from tools.rag_tools import rag_retrieve_content as _rag_retrieve_content
except Exception:  # pragma: no cover - optional RAG dependency/import guard
    _rag_retrieve_content = None


T = TypeVar("T")


class BuildPlanInput(BaseModel):
    user_id: str = Field(..., min_length=1)
    exam_id_or_name: str = Field(..., min_length=1)
    duration_days: int = Field(..., ge=2, le=7)
    start_date: str | None = None
    name: str = "Learner"
    level: str = "beginner"
    email: str | None = None
    user_goal: str | None = None


class CustomRagPlanInput(BaseModel):
    user_id: str = Field(..., min_length=1)
    duration_days: int = Field(..., ge=2, le=7)
    start_date: str | None = None
    name: str = "Learner"
    level: str = "beginner"
    email: str | None = None
    user_goal: str | None = None


class UserIdInput(BaseModel):
    user_id: str = Field(..., min_length=1)


class TeachPlanDayInput(BaseModel):
    plan_day_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)


class LessonForTopicInput(BaseModel):
    topic_name: str = Field(..., min_length=1)
    level: str = "beginner"


class GenerateQuizInput(BaseModel):
    user_id: str = Field(..., min_length=1)
    topic_id: str = Field(..., min_length=1)
    num_questions: int = Field(5, ge=1, le=20)
    difficulty: int = Field(3, ge=1, le=5)
    plan_day_id: str | None = None


class SubmitQuizInput(BaseModel):
    attempt_id: str = Field(..., min_length=1)
    user_answers: list[int]
    time_taken_secs: int = Field(..., ge=1)


class RagRetrieveContentInput(BaseModel):
    query: str = Field(..., min_length=1)
    topic_id: str = ""
    top_k: int = Field(5, ge=1, le=20)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _success(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": _json_safe(data)}


def _tool_error(exc: Exception) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        },
    }


def _run_safely(fn: Callable[[], T]) -> dict[str, Any]:
    try:
        return _success(fn())
    except Exception as exc:
        return _tool_error(exc)


async def _run_async_safely(fn: Callable[[], Awaitable[T]]) -> dict[str, Any]:
    try:
        return _success(await fn())
    except Exception as exc:
        return _tool_error(exc)


@tool("study_build_plan", args_schema=BuildPlanInput)
def study_build_plan(
    user_id: str,
    exam_id_or_name: str,
    duration_days: int,
    start_date: str | None = None,
    name: str = "Learner",
    level: str = "beginner",
    email: str | None = None,
    user_goal: str | None = None,
) -> dict[str, Any]:
    """Create a Supabase-backed study plan using the existing planner workflow."""
    return _run_safely(
        lambda: study_core.run_plan_workflow(
            user_id=user_id,
            exam_id_or_name=exam_id_or_name,
            duration_days=duration_days,
            start_date=start_date,
            name=name,
            level=level,
            email=email,
            user_goal=user_goal,
        )
    )


@tool("study_build_custom_rag_plan", args_schema=CustomRagPlanInput)
def study_build_custom_rag_plan(
    user_id: str,
    duration_days: int,
    start_date: str | None = None,
    name: str = "Learner",
    level: str = "beginner",
    email: str | None = None,
    user_goal: str | None = None,
) -> dict[str, Any]:
    """Create a custom study plan from available RAG documents and syllabus content."""
    return _run_safely(
        lambda: study_core.run_custom_rag_plan_workflow(
            user_id=user_id,
            duration_days=duration_days,
            start_date=start_date,
            name=name,
            level=level,
            email=email,
            user_goal=user_goal,
        )
    )


@tool("study_get_active_plan", args_schema=UserIdInput)
def study_get_active_plan(user_id: str) -> dict[str, Any]:
    """Fetch the user's active study plan from Supabase."""
    return _run_safely(lambda: {"plan": study_core.get_active_plan(user_id)})


@tool("study_get_user_profile", args_schema=UserIdInput)
def study_get_user_profile(user_id: str) -> dict[str, Any]:
    """Fetch the user's profile, active plan, and progress summary."""
    return _run_safely(lambda: study_core.get_user_profile(user_id))


@tool("study_teach_plan_day", args_schema=TeachPlanDayInput)
def study_teach_plan_day(plan_day_id: str, user_id: str) -> dict[str, Any]:
    """Teach one plan day using existing lesson, revision, and personalization logic."""
    return _run_safely(lambda: study_core.teach_plan_day(plan_day_id=plan_day_id, user_id=user_id))


@tool("study_lesson_for_topic", args_schema=LessonForTopicInput)
def study_lesson_for_topic(topic_name: str, level: str = "beginner") -> dict[str, Any]:
    """Generate a lightweight lesson for a named topic."""
    return _run_safely(
        lambda: {"lesson_content": study_core.lesson_for_topic(topic_name=topic_name, level=level)}
    )


@tool("study_generate_quiz", args_schema=GenerateQuizInput)
def study_generate_quiz(
    user_id: str,
    topic_id: str,
    num_questions: int = 5,
    difficulty: int = 3,
    plan_day_id: str | None = None,
) -> dict[str, Any]:
    """Generate and persist an adaptive quiz attempt for a topic."""
    return _run_safely(
        lambda: study_core.generate_quiz(
            user_id=user_id,
            topic_id=topic_id,
            num_questions=num_questions,
            difficulty=difficulty,
            plan_day_id=plan_day_id,
        )
    )


@tool("study_submit_quiz", args_schema=SubmitQuizInput)
def study_submit_quiz(
    attempt_id: str,
    user_answers: list[int],
    time_taken_secs: int,
) -> dict[str, Any]:
    """Score a quiz attempt and update user performance using existing business logic."""
    return _run_safely(
        lambda: study_core.submit_quiz(
            attempt_id=attempt_id,
            user_answers=user_answers,
            time_taken_secs=time_taken_secs,
        )
    )


@tool("study_get_progress", args_schema=UserIdInput)
def study_get_progress(user_id: str) -> dict[str, Any]:
    """Fetch topic performance, weak areas, activity, streak, and badge progress."""
    return _run_safely(lambda: study_core.get_progress(user_id))


@tool("study_replan_user", args_schema=UserIdInput)
def study_replan_user(user_id: str) -> dict[str, Any]:
    """Reorder remaining study days based on current weak-area performance."""
    return _run_safely(lambda: study_core.replan_user(user_id))


@tool("study_rag_retrieve_content", args_schema=RagRetrieveContentInput)
async def study_rag_retrieve_content(
    query: str,
    topic_id: str = "",
    top_k: int = 5,
) -> dict[str, Any]:
    """Retrieve study context from Supabase RAG chunks, with syllabus fallback."""
    if _rag_retrieve_content is None:
        return _tool_error(RuntimeError("RAG retrieval tool is unavailable"))
    return await _run_async_safely(
        lambda: _rag_retrieve_content.ainvoke(
            {
                "query": query,
                "topic_id": topic_id,
                "top_k": top_k,
            }
        )
    )


STUDY_CORE_TOOLS: list[BaseTool] = [
    study_build_plan,
    study_build_custom_rag_plan,
    study_get_active_plan,
    study_get_user_profile,
    study_teach_plan_day,
    study_lesson_for_topic,
    study_generate_quiz,
    study_submit_quiz,
    study_get_progress,
    study_replan_user,
    study_rag_retrieve_content,
]

STUDY_CORE_TOOL_MAP: dict[str, BaseTool] = {item.name: item for item in STUDY_CORE_TOOLS}


__all__ = [
    "BuildPlanInput",
    "CustomRagPlanInput",
    "GenerateQuizInput",
    "LessonForTopicInput",
    "RagRetrieveContentInput",
    "STUDY_CORE_TOOL_MAP",
    "STUDY_CORE_TOOLS",
    "SubmitQuizInput",
    "TeachPlanDayInput",
    "UserIdInput",
]
