from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agents import run_study_task
from agents.langgraph_workflow import run_study_graph, stream_study_graph_events
from agents.llm import LLMConfigurationError


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


class AgentRequest(BaseModel):
    user_id: str = Field(..., min_length=1, description="Application user identifier.")
    message: str = Field(..., min_length=1, description="Natural-language study request.")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured context such as plan_day_id, topic_id, or UI state.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "learner-123",
                "message": "Teach my current plan day",
                "context": {"plan_day_id": "day-abc"},
            }
        }
    }


class AgentResponse(BaseModel):
    agent: str = Field(..., description="Routed specialist agent.")
    task: str = Field(..., description="Resolved task name.")
    message: str = Field(..., description="Concise user-facing status or result message.")
    data: dict[str, Any] = Field(default_factory=dict, description="Structured task result.")
    events: list[Any] = Field(default_factory=list, description="Operational graph events.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "agent": "teacher",
                "task": "teach_day",
                "message": "Opening your lesson.",
                "data": {"topic_name": "Percentage", "status": "taught"},
                "events": [{"node": "supervisor", "agent": "teacher", "task": "teach_day"}],
            }
        }
    }


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _agent_event_stream(input_data: dict[str, Any]):
    for item in stream_study_graph_events(input_data):
        event = str(item.get("event") or "message")
        data = item.get("data") or {}
        yield _sse(event, data)


@router.post("/agent", response_model=AgentResponse)
async def run_study_agent(req: AgentRequest) -> AgentResponse:
    try:
        result = run_study_graph(
            {
                "user_id": req.user_id,
                "message": req.message,
                "context": req.context,
            }
        )
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Study agent failed: {exc}") from exc

    if not isinstance(result, dict):
        raise HTTPException(status_code=500, detail="Study agent returned an invalid response")
    if result.get("data", {}).get("ok") is False or "error" in result or "error" in result.get("data", {}):
        raise HTTPException(status_code=502, detail=result.get("error") or result.get("data", {}).get("error") or result)
    return AgentResponse(**result)


@router.post("/agent/stream")
async def run_study_agent_stream(req: AgentRequest) -> StreamingResponse:
    return StreamingResponse(
        _agent_event_stream(
            {
                "user_id": req.user_id,
                "message": req.message,
                "context": req.context,
            }
        ),
        media_type="text/event-stream",
    )


@router.get("/agent/stream")
async def run_study_agent_stream_get(
    user_id: str = Query(..., min_length=1),
    message: str = Query(..., min_length=1),
    context: str | None = None,
) -> StreamingResponse:
    parsed_context: dict[str, Any] = {}
    if context:
        try:
            raw = json.loads(context)
            if isinstance(raw, dict):
                parsed_context = raw
            else:
                raise ValueError("context must be a JSON object")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamingResponse(
        _agent_event_stream(
            {
                "user_id": user_id,
                "message": message,
                "context": parsed_context,
            }
        ),
        media_type="text/event-stream",
    )


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


@router.post("/custom-plan", response_model=OnboardResponse)
async def create_custom_rag_plan(req: OnboardRequest) -> OnboardResponse:
    result = run_study_task(
        "build_custom_rag_plan",
        user_id=req.user_id,
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
        message=result.get("message")
        or f"Custom RAG plan created: plan_id={plan['plan_id']}, {plan['duration_days']} days starting {plan['start_date']}",
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
    def events():
        final_data: dict[str, Any] | None = None
        for item in stream_study_graph_events(
            {
                "user_id": user_id,
                "message": f"Teach plan day {plan_day_id}",
                "context": {
                    "plan_day_id": plan_day_id,
                    "preferred_agent": "teacher",
                    "preferred_tool": "study_teach_plan_day",
                },
            }
        ):
            event = str(item.get("event") or "message")
            data = item.get("data") or {}
            if event == "final_response":
                final_data = data.get("data") if isinstance(data, dict) else None
            yield _sse(event, data)
        if final_data is not None:
            yield _sse("complete", final_data)

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
