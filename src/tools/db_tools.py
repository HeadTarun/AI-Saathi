from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from langchain_core.tools import tool

import study_core
from db import get_supabase


def _rows(response: Any) -> list[dict[str, Any]]:
    return getattr(response, "data", None) or []


@tool
async def get_user_profile(user_id: str) -> dict:
    """Fetch a user profile from Supabase."""
    rows = _rows(get_supabase().table("users").select("*").eq("id", user_id).limit(1).execute())
    if not rows:
        raise ValueError(f"User {user_id} not found")
    return rows[0]


@tool
async def get_exam_syllabus(
    exam_id: str,
    subject: str | None = None,
    min_priority: str | None = None,
) -> list[dict]:
    """Fetch syllabus topics for an exam from Supabase."""
    topics = study_core.list_topics(exam_id)
    if subject:
        topics = [topic for topic in topics if topic["subject"] == subject]
    if min_priority:
        priority_order = {"HIGH": 1, "MED": 2, "LOW": 3}
        cap = priority_order.get(min_priority, 3)
        topics = [topic for topic in topics if priority_order.get(topic["priority"], 3) <= cap]
    return topics


@tool
async def fetch_weak_areas(user_id: str, limit: int = 5) -> list[dict]:
    """Fetch the user's weakest topics from Supabase-backed performance data."""
    return study_core.get_progress(user_id)["top_weaknesses"][:limit]


@tool
async def get_topic_details(topic_id: str) -> dict:
    """Fetch one syllabus topic from Supabase."""
    rows = _rows(
        get_supabase()
        .table("syllabus_topics")
        .select("*")
        .eq("id", topic_id)
        .limit(1)
        .execute()
    )
    if not rows:
        raise ValueError(f"Topic {topic_id} not found")
    row = rows[0]
    row["topic_id"] = row["id"]
    return row


@tool
async def fetch_plan_day(plan_day_id: str) -> dict:
    """Fetch one study plan day from Supabase."""
    found = study_core.get_plan_by_day(plan_day_id)
    if not found:
        raise ValueError(f"Plan day {plan_day_id} not found")
    return found[1]


@tool
async def fetch_teaching_history(user_id: str, topic_id: str) -> dict:
    """Fetch recent teaching history for a user and topic from Supabase."""
    rows = _rows(
        get_supabase()
        .table("teaching_logs")
        .select("*")
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .order("taught_at", desc=True)
        .execute()
    )
    last = rows[0] if rows else {}
    return {
        "previously_taught": bool(rows),
        "last_summary": last.get("content_summary"),
        "last_taught_at": last.get("taught_at"),
        "session_count": len(rows),
    }


@tool
async def store_teaching_log(
    plan_day_id: str,
    user_id: str,
    topic_id: str,
    content_summary: str,
    revision_covered: list[str],
    llm_trace: dict,
    duration_mins: int,
) -> dict:
    """Store a teaching log in Supabase."""
    log_id = study_core._new_id("log")
    get_supabase().table("teaching_logs").insert(
        {
            "id": log_id,
            "plan_day_id": plan_day_id,
            "user_id": user_id,
            "topic_id": topic_id,
            "content_summary": content_summary,
            "revision_covered": revision_covered,
            "llm_trace": llm_trace,
            "duration_mins": duration_mins,
        }
    ).execute()
    return {"log_id": log_id}


@tool
async def mark_day_taught(plan_day_id: str) -> dict:
    """Mark a Supabase study plan day as taught."""
    taught_at = datetime.now().isoformat(timespec="seconds")
    (
        get_supabase()
        .table("study_plan_days")
        .update({"status": "taught", "taught_at": taught_at})
        .eq("id", plan_day_id)
        .execute()
    )
    return {"status": "taught", "taught_at": taught_at}


@tool
async def store_quiz_attempt(
    user_id: str,
    topic_id: str,
    questions: list[dict],
    plan_day_id: str | None = None,
    template_id: str | None = None,
) -> dict:
    """Store a quiz attempt in Supabase."""
    attempt_id = study_core._new_id("attempt")
    get_supabase().table("quiz_attempts").insert(
        {
            "id": attempt_id,
            "user_id": user_id,
            "topic_id": topic_id,
            "plan_day_id": plan_day_id,
            "template_id": template_id,
            "questions": questions,
            "total_questions": len(questions),
        }
    ).execute()
    return {"attempt_id": attempt_id}


@tool
async def submit_quiz_attempt(
    attempt_id: str,
    user_answers: list[int],
    time_taken_secs: int,
) -> dict:
    """Score and submit a Supabase-backed quiz attempt."""
    return study_core.submit_quiz(attempt_id, user_answers, time_taken_secs)


@tool
async def update_user_performance(
    user_id: str,
    topic_id: str,
    new_correct: int,
    new_attempts: int,
    avg_time_secs: float,
) -> dict:
    """Update a user's Supabase-backed performance row."""
    current = _rows(
        get_supabase()
        .table("user_performance")
        .select("*")
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .limit(1)
        .execute()
    )
    row = current[0] if current else {}
    attempts = int(row.get("attempts") or 0) + new_attempts
    correct = int(row.get("correct") or 0) + new_correct
    accuracy = round(correct * 100 / attempts, 2) if attempts else 0.0
    weakness_score = round((1 - accuracy / 100) * 70 + 9, 2)
    get_supabase().table("user_performance").upsert(
        {
            "id": row.get("id") or study_core._new_id("perf"),
            "user_id": user_id,
            "topic_id": topic_id,
            "attempts": attempts,
            "correct": correct,
            "accuracy": accuracy,
            "avg_time_secs": avg_time_secs,
            "weakness_score": weakness_score,
            "last_attempted": datetime.now().isoformat(timespec="seconds"),
        },
        on_conflict="user_id,topic_id",
    ).execute()
    return {"updated_accuracy": accuracy, "new_weakness_score": weakness_score}


@tool
async def refresh_weak_areas(user_id: str) -> dict:
    """Return refreshed weakness summary from Supabase-backed performance data."""
    top = study_core.get_progress(user_id)["top_weaknesses"]
    return {"refreshed_count": len(top), "top_weak_topic": top[0]["topic_name"] if top else None}


@tool
async def flag_replan(
    user_id: str,
    reason: str,
    affected_topic_ids: list[str],
) -> dict:
    """Flag the active Supabase study plan for replanning."""
    plan = study_core.get_active_plan(user_id)
    if not plan:
        return {"replan_scheduled": False, "plan_id": None}
    meta = plan.get("meta") or {}
    meta.update(
        {
            "replan_flag": True,
            "replan_reason": reason,
            "affected_topics": affected_topic_ids,
            "flagged_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    get_supabase().table("study_plans").update({"meta": meta}).eq("id", plan["id"]).execute()
    return {"replan_scheduled": True, "plan_id": plan["id"]}


@tool
async def compute_topic_order(
    topics: list[dict],
    weak_areas: list[dict],
    duration_days: int,
) -> dict:
    """Compute an ordered study plan from topic and weakness inputs."""
    weak_map = {weak["topic_id"]: weak.get("weakness_score", 0) for weak in weak_areas}
    start = date.today().isoformat()
    ordered_plan = study_core.compute_ordered_plan_days(
        topics=[
            {
                "id": topic.get("id") or topic["topic_id"],
                "name": topic.get("name") or topic.get("topic_name") or topic["topic_id"],
                "priority": topic.get("priority", "LOW"),
                "difficulty": topic.get("difficulty", 3),
            }
            for topic in topics
            if topic.get("id") or topic.get("topic_id")
        ],
        weak_scores=weak_map,
        duration_days=duration_days,
        start_date=start,
    )
    return {
        "ordered_plan": [
            {
                "day": day["day_number"],
                "topic_id": day["topic_id"],
                "topic_name": day["topic_name"],
                "revision_ids": day["revision_topic_ids"],
                "allocated_mins": day["allocated_minutes"],
                "scheduled_date": day["scheduled_date"],
                "reason": day["reason"],
            }
            for day in ordered_plan
        ]
    }


@tool
async def create_study_plan(
    user_id: str,
    exam_id: str,
    start_date: str,
    end_date: str,
    name: str = "Learner",
    level: str = "beginner",
) -> dict:
    """Create a Supabase-backed study plan header row without day rows."""
    duration = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1
    plan = study_core.create_study_plan_record(
        user_id=user_id,
        exam_id_or_name=exam_id,
        duration_days=duration,
        start_date=start_date,
        name=name,
        level=level,
        meta={"workflow": "tool_create_study_plan"},
    )
    return {"plan_id": plan["id"], "planner_version": study_core.PLANNER_VERSION}


@tool
async def create_plan_days(
    plan_id: str,
    ordered_plan: list[dict],
    start_date: str,
) -> dict:
    """Create Supabase-backed study plan day rows."""
    base = date.fromisoformat(start_date)
    ordered_days = [
        {
            "day_number": item["day"],
            "scheduled_date": (base + timedelta(days=item["day"] - 1)).isoformat(),
            "topic_id": item["topic_id"],
            "revision_topic_ids": item.get("revision_ids", []),
            "allocated_minutes": item.get("allocated_mins", 90),
            "status": "pending",
        }
        for item in ordered_plan
        if item.get("topic_id")
    ]
    rows = study_core.create_study_plan_days(plan_id, ordered_days)
    return {"days_created": len(rows)}


@tool
async def run_planner_workflow(
    user_id: str,
    exam_id: str,
    duration_days: int,
    start_date: str | None = None,
    name: str = "Learner",
    level: str = "beginner",
) -> dict:
    """Run the full Supabase-backed planner loop and return the created plan."""
    result = study_core.run_plan_workflow(
        user_id=user_id,
        exam_id_or_name=exam_id,
        duration_days=duration_days,
        start_date=start_date,
        name=name,
        level=level,
    )
    return {
        "plan_id": result["plan"]["plan_id"],
        "plan": result["plan"],
        "workflow": result["workflow"],
    }


@tool
async def update_study_plan_from_progress(user_id: str) -> dict:
    """Update pending Supabase plan days using current weak-area performance."""
    return study_core.replan_user(user_id)
