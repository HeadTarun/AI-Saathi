"""
FastAPI routes for AI Study Companion.
All endpoints are async. Agents are invoked via ainvoke().
Streaming is not used in MVP - standard JSON responses only.
"""

import json
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from agents.planner_agent import planner_agent
from agents.progress_analyzer_agent import run_progress_analysis
from agents.quiz_agent import quiz_agent
from agents.teacher_agent import teacher_agent
from db import get_pool

router = APIRouter(prefix="/study", tags=["Study Companion"])


class OnboardRequest(BaseModel):
    user_id: str = Field(..., description="UUID of existing user")
    exam_id: str = Field(..., description="UUID of target exam")
    duration_days: int = Field(..., ge=2, le=7, description="Plan length in days (2-7 for MVP)")
    start_date: str | None = Field(None, description="YYYY-MM-DD; defaults to today")


class OnboardResponse(BaseModel):
    plan_id: str
    start_date: str
    end_date: str
    duration_days: int
    message: str


class TeachResponse(BaseModel):
    log_id: str
    lesson_content: str
    topic_name: str
    status: str


class QuizGenerateRequest(BaseModel):
    user_id: str
    topic_id: str
    num_questions: int = Field(10, ge=3, le=20)
    difficulty: int = Field(3, ge=1, le=5)
    plan_day_id: str | None = None


class QuizGenerateResponse(BaseModel):
    attempt_id: str
    questions: list[dict[str, Any]]
    total: int


class QuizSubmitRequest(BaseModel):
    user_answers: list[int] = Field(..., description="List of chosen option indices (0-3)")
    time_taken_secs: int = Field(..., ge=1)


class QuizSubmitResponse(BaseModel):
    score: int
    total: int
    accuracy: float
    per_question_result: list[bool]
    updated_accuracy: float
    new_weakness_score: float
    replan_triggered: bool
    top_weak_topics: list[dict[str, Any]]


class ProgressResponse(BaseModel):
    topic_stats: list[dict[str, Any]]
    top_weaknesses: list[dict[str, Any]]


class ReplanResponse(BaseModel):
    updated_plan_id: str
    message: str


def _extract_plan_id(agent_response: str) -> str:
    """Parse plan_id from Planner Agent's final message."""
    match = re.search(r"plan_id=([a-f0-9-]{36})", agent_response, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract plan_id from: {agent_response}")


def _sanitize_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove correct_index and explanation before sending to frontend."""
    return [
        {
            "question_text": question["question_text"],
            "options": question["options"],
        }
        for question in questions
    ]


def _parse_json_content(content: str) -> dict[str, Any]:
    clean = content.strip()
    if "```" in clean:
        clean = re.sub(r"```(?:json|[a-zA-Z0-9_-]+)?", "", clean)
        clean = clean.replace("```", "").strip()
    return json.loads(clean)


def _jsonb_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


async def _get_plan_days(plan_id: str, pool) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT spd.id::text, spd.day_number, spd.scheduled_date::text,
                   st.topic_name, spd.allocated_minutes, spd.status
            FROM study_plan_days spd
            JOIN syllabus_topics st ON st.id = spd.topic_id
            WHERE spd.plan_id = $1::uuid
            ORDER BY spd.day_number
            """,
            plan_id,
        )
    return [dict(row) for row in rows]


@router.post("/onboard", response_model=OnboardResponse)
async def onboard_user(req: OnboardRequest) -> OnboardResponse:
    """
    Trigger Planner Agent to create a study plan.
    duration_days: 2-7 days (MVP constraint).
    start_date defaults to today in Asia/Kolkata.
    """
    start = req.start_date or datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    end = (date.fromisoformat(start) + timedelta(days=req.duration_days - 1)).isoformat()

    input_msg = HumanMessage(
        content=f"""
Create a study plan with these parameters:
- user_id: {req.user_id}
- exam_id: {req.exam_id}
- duration_days: {req.duration_days}
- start_date: {start}
- end_date: {end}
"""
    )

    try:
        result = await planner_agent.ainvoke({"messages": [input_msg]})
        final_msg = result["messages"][-1].content
        plan_id = _extract_plan_id(final_msg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Planner Agent error: {exc}") from exc

    return OnboardResponse(
        plan_id=plan_id,
        start_date=start,
        end_date=end,
        duration_days=req.duration_days,
        message=final_msg,
    )


@router.get("/plan/{user_id}")
async def get_user_plan(user_id: str) -> dict[str, Any]:
    """Fetch the active study plan and all plan days for a user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        plan = await conn.fetchrow(
            """
            SELECT id::text, exam_id::text, start_date::text, end_date::text,
                   duration_days, status, planner_version, created_at::text
            FROM study_plans
            WHERE user_id = $1::uuid AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )

    if not plan:
        raise HTTPException(status_code=404, detail="No active plan found for user")

    days = await _get_plan_days(plan["id"], pool)
    return {"study_plan": dict(plan), "study_plan_days": days}


@router.post("/teach/{plan_day_id}", response_model=TeachResponse)
async def teach_day(plan_day_id: str, user_id: str) -> TeachResponse:
    """
    Trigger Teacher Agent for a specific plan day.
    Idempotent: if already taught, returns the existing log summary.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT tl.id::text, tl.content_summary, spd.status, st.topic_name
            FROM study_plan_days spd
            JOIN syllabus_topics st ON st.id = spd.topic_id
            LEFT JOIN teaching_logs tl ON tl.plan_day_id = spd.id
            WHERE spd.id = $1::uuid
            ORDER BY tl.taught_at DESC
            LIMIT 1
            """,
            plan_day_id,
        )

    if not existing:
        raise HTTPException(status_code=404, detail="Plan day not found")

    if existing["status"] == "taught":
        return TeachResponse(
            log_id=existing["id"] or "",
            lesson_content=existing["content_summary"] or "(already taught - see teaching_logs)",
            topic_name=existing["topic_name"],
            status="taught",
        )

    input_msg = HumanMessage(
        content=f"""
Teach today's lesson:
- plan_day_id: {plan_day_id}
- user_id: {user_id}
"""
    )

    try:
        result = await teacher_agent.ainvoke({"messages": [input_msg]})
        lesson_content = result["messages"][-1].content
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Teacher Agent error: {exc}") from exc

    async with pool.acquire() as conn:
        log_row = await conn.fetchrow(
            """
            SELECT tl.id::text, st.topic_name
            FROM teaching_logs tl
            JOIN syllabus_topics st ON st.id = tl.topic_id
            WHERE tl.plan_day_id = $1::uuid
            ORDER BY tl.taught_at DESC
            LIMIT 1
            """,
            plan_day_id,
        )

    return TeachResponse(
        log_id=log_row["id"] if log_row else "",
        lesson_content=lesson_content,
        topic_name=log_row["topic_name"] if log_row else existing["topic_name"],
        status="taught",
    )


@router.post("/quiz/generate", response_model=QuizGenerateResponse)
async def generate_quiz(req: QuizGenerateRequest) -> QuizGenerateResponse:
    """Generate a quiz for a topic and return sanitized questions."""
    input_msg = HumanMessage(
        content=f"""
Generate a quiz:
- user_id: {req.user_id}
- topic_id: {req.topic_id}
- num_questions: {req.num_questions}
- difficulty: {req.difficulty}
- plan_day_id: {req.plan_day_id or "null"}
"""
    )

    try:
        result = await quiz_agent.ainvoke({"messages": [input_msg]})
        raw = result["messages"][-1].content
        if raw.strip().startswith("ERROR:"):
            raise HTTPException(status_code=400, detail=raw.strip())
        parsed = _parse_json_content(raw)
        attempt_id = parsed["attempt_id"]
        questions = parsed["questions"]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Quiz Agent error: {exc}") from exc

    return QuizGenerateResponse(
        attempt_id=attempt_id,
        questions=_sanitize_questions(questions),
        total=len(questions),
    )


@router.post("/quiz/{attempt_id}/submit", response_model=QuizSubmitResponse)
async def submit_quiz(attempt_id: str, req: QuizSubmitRequest) -> QuizSubmitResponse:
    """Submit quiz answers, score server-side, then run progress analysis."""
    submit_msg = HumanMessage(
        content=f"""
Submit quiz answers:
- attempt_id: {attempt_id}
- user_answers: {req.user_answers}
- time_taken_secs: {req.time_taken_secs}
"""
    )

    try:
        quiz_result = await quiz_agent.ainvoke({"messages": [submit_msg]})
        score_data = _parse_json_content(quiz_result["messages"][-1].content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Quiz submit error: {exc}") from exc

    try:
        progress_data = await run_progress_analysis(attempt_id)
    except Exception:
        progress_data = {
            "updated_accuracy": score_data.get("accuracy", 0),
            "new_weakness_score": 50.0,
            "top_weak_topics": [],
            "replan_triggered": False,
        }

    return QuizSubmitResponse(
        score=score_data["score"],
        total=score_data["total"],
        accuracy=score_data["accuracy"],
        per_question_result=score_data["per_question_result"],
        updated_accuracy=progress_data.get("updated_accuracy") or score_data.get("accuracy", 0),
        new_weakness_score=progress_data.get("new_weakness_score") or 50.0,
        replan_triggered=bool(progress_data.get("replan_triggered")),
        top_weak_topics=progress_data.get("top_weak_topics") or [],
    )


@router.get("/progress/{user_id}", response_model=ProgressResponse)
async def get_progress(user_id: str) -> ProgressResponse:
    """Fetch user performance stats and top weaknesses."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        topic_stats = await conn.fetch(
            """
            SELECT st.topic_name, up.attempts, up.correct, up.accuracy,
                   up.avg_time_secs, up.weakness_score, up.last_attempted::text
            FROM user_performance up
            JOIN syllabus_topics st ON st.id = up.topic_id
            WHERE up.user_id = $1::uuid
            ORDER BY up.weakness_score DESC
            """,
            user_id,
        )
        top_weaknesses = await conn.fetch(
            """
            SELECT st.topic_name, wa.weakness_score, wa.rank, wa.recommended_extra_mins
            FROM weak_areas wa
            JOIN syllabus_topics st ON st.id = wa.topic_id
            WHERE wa.user_id = $1::uuid
            ORDER BY wa.rank ASC
            LIMIT 10
            """,
            user_id,
        )

    return ProgressResponse(
        topic_stats=[dict(row) for row in topic_stats],
        top_weaknesses=[dict(row) for row in top_weaknesses],
    )


@router.post("/replan/{user_id}", response_model=ReplanResponse)
async def replan(user_id: str) -> ReplanResponse:
    """Trigger Planner Agent to adjust remaining plan days."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        plan = await conn.fetchrow(
            """
            SELECT id::text, end_date::text, meta
            FROM study_plans
            WHERE user_id = $1::uuid AND status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
        )

    if not plan:
        raise HTTPException(status_code=404, detail="No active plan to replan")

    meta = _jsonb_dict(plan["meta"])
    reason = meta.get("replan_reason", "Manual replan requested")
    affected = meta.get("affected_topics", [])

    today = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    new_end = plan["end_date"]

    async with pool.acquire() as conn:
        remaining = await conn.fetchval(
            """
            SELECT COUNT(*)
            FROM study_plan_days
            WHERE plan_id = $1::uuid
              AND status = 'pending'
              AND scheduled_date >= $2::date
            """,
            plan["id"],
            today,
        )

    input_msg = HumanMessage(
        content=f"""
Re-plan for user_id: {user_id}
Reason: {reason}
Affected topics: {affected}
Remaining pending days: {remaining}
New start_date: {today}
New end_date: {new_end}

Only re-schedule the REMAINING days (status='pending').
Do not change days that are already 'taught'.
"""
    )

    try:
        result = await planner_agent.ainvoke({"messages": [input_msg]})
        final_msg = result["messages"][-1].content
        new_plan_id = _extract_plan_id(final_msg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Replan error: {exc}") from exc

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE study_plans
            SET meta = meta - 'replan_flag' - 'replan_reason' - 'affected_topics'
            WHERE user_id = $1::uuid AND status = 'active'
            """,
            user_id,
        )

    return ReplanResponse(updated_plan_id=new_plan_id, message=final_msg)
