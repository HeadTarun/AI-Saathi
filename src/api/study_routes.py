from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents import run_study_task


router = APIRouter(prefix="/study", tags=["Study Companion"])


class OnboardRequest(BaseModel):
    user_id: str
    exam_id: str
    duration_days: int = Field(..., ge=2, le=7)
    start_date: str | None = None
    name: str = "Learner"
    email: str | None = None
    level: str = "beginner"
    user_goal: str | None = None


class OnboardResponse(BaseModel):
    plan_id: str
    start_date: str
    end_date: str
    duration_days: int
    message: str


class TeachResponse(BaseModel):
    log_id: str
    lesson_content: str
    lesson_steps: list[dict[str, Any]] = Field(default_factory=list)
    revision: dict[str, Any] | None = None
    teacher_status: str = "complete"
    topic_name: str
    status: str
    personalization: dict[str, Any] = Field(default_factory=dict)


class QuizGenerateRequest(BaseModel):
    user_id: str
    topic_id: str
    num_questions: int = Field(5, ge=1, le=20)
    difficulty: int = Field(3, ge=1, le=5)
    plan_day_id: str | None = None


class QuizGenerateResponse(BaseModel):
    attempt_id: str
    questions: list[dict[str, Any]]
    total: int
    adaptive_context: dict[str, Any] = Field(default_factory=dict)


class QuizSubmitRequest(BaseModel):
    user_answers: list[int]
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
    passed: bool
    pass_mark: int
    next_day_unlocked: bool
    recommended_action: str


class ProgressResponse(BaseModel):
    topic_stats: list[dict[str, Any]]
    top_weaknesses: list[dict[str, Any]]
    activity: dict[str, Any] = Field(default_factory=dict)


class ReplanResponse(BaseModel):
    updated_plan_id: str
    message: str


class ProfileResponse(BaseModel):
    user: dict[str, Any]
    active_plan: dict[str, Any] | None = None
    progress: dict[str, Any]
    source: str = "supabase"


@router.get("/exams")
async def list_study_goals() -> dict[str, Any]:
    return {"exams": run_study_task("list_exams")["exams"]}


@router.get("/profile/{user_id}", response_model=ProfileResponse)
async def get_user_profile(user_id: str) -> ProfileResponse:
    try:
        result = run_study_task("get_profile", user_id=user_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ProfileResponse(**result)


@router.post("/onboard", response_model=OnboardResponse)
async def onboard_user(req: OnboardRequest) -> OnboardResponse:
    result = run_study_task(
        "build_plan",
        user_id=req.user_id,
        exam_id_or_name=req.exam_id,
        duration_days=req.duration_days,
        start_date=req.start_date,
        name=req.name,
        email=req.email,
        level=req.level,
        user_goal=req.user_goal,
    )
    plan = result["plan"]
    return OnboardResponse(
        plan_id=plan["plan_id"],
        start_date=plan["start_date"],
        end_date=plan["end_date"],
        duration_days=plan["duration_days"],
        message=f"Plan created: plan_id={plan['plan_id']}, {plan['duration_days']} days starting {plan['start_date']}",
    )


@router.get("/plan/{user_id}")
async def get_user_plan(user_id: str) -> dict[str, Any]:
    try:
        plan = run_study_task("get_plan", user_id=user_id)["plan"]
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"study_plan": {key: value for key, value in plan.items() if key != "days"}, "study_plan_days": plan["days"]}


@router.post("/teach/{plan_day_id}", response_model=TeachResponse)
async def teach_day(plan_day_id: str, user_id: str) -> TeachResponse:
    try:
        result = run_study_task("teach_day", plan_day_id=plan_day_id, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TeachResponse(**result)


@router.get("/teach/{plan_day_id}/stream")
async def teach_day_stream(plan_day_id: str, user_id: str) -> StreamingResponse:
    async def events():
        for status, message in [
            ("preparing", "Preparing your lesson"),
            ("reviewing", "Checking what to revise"),
            ("explaining", "Building the concept"),
            ("practice", "Preparing one practice step"),
        ]:
            yield f"event: {status}\ndata: {json.dumps({'message': message})}\n\n"
            await asyncio.sleep(0.1)
        try:
            result = run_study_task("teach_day", plan_day_id=plan_day_id, user_id=user_id)
            yield f"event: complete\ndata: {json.dumps(result, default=str)}\n\n"
        except ValueError as exc:
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/quiz/generate", response_model=QuizGenerateResponse)
async def generate_quiz(req: QuizGenerateRequest) -> QuizGenerateResponse:
    result = run_study_task(
        "generate_quiz",
        user_id=req.user_id,
        topic_id=req.topic_id,
        num_questions=req.num_questions,
        difficulty=req.difficulty,
        plan_day_id=req.plan_day_id,
    )
    return QuizGenerateResponse(**result)


@router.post("/quiz/{attempt_id}/submit", response_model=QuizSubmitResponse)
async def submit_quiz(attempt_id: str, req: QuizSubmitRequest) -> QuizSubmitResponse:
    try:
        result = run_study_task(
            "submit_quiz",
            attempt_id=attempt_id,
            user_answers=req.user_answers,
            time_taken_secs=req.time_taken_secs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QuizSubmitResponse(**result)


@router.get("/progress/{user_id}", response_model=ProgressResponse)
async def get_progress(user_id: str) -> ProgressResponse:
    return ProgressResponse(**run_study_task("get_progress", user_id=user_id))


@router.post("/replan/{user_id}", response_model=ReplanResponse)
async def replan(user_id: str) -> ReplanResponse:
    try:
        result = run_study_task("replan", user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ReplanResponse(**result)
