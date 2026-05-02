"""
All DB-backed ReAct tools.
Every function is decorated with @tool so LangGraph can call it during agent loops.
Input/output types are documented; do not change signatures without updating agent prompts.
"""

import json
from collections import defaultdict, deque
from datetime import UTC, date, datetime, timedelta

from langchain_core.tools import tool

from src.db import get_pool


@tool
async def get_user_profile(user_id: str) -> dict:
    """
    Fetch user profile including level, target exam, and timezone.
    Call this as the FIRST action in every agent run to establish user context.

    Args:
        user_id: UUID string of the user

    Returns:
        dict with keys: id, name, level, target_exam_id, timezone, created_at
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id::text, u.name, u.level, u.target_exam_id::text,
                   u.timezone, u.created_at::text
            FROM users u
            WHERE u.id = $1::uuid
            """,
            user_id,
        )
    if not row:
        raise ValueError(f"User {user_id} not found")
    return dict(row)


@tool
async def get_exam_syllabus(
    exam_id: str,
    subject: str | None = None,
    min_priority: str | None = None,
) -> list[dict]:
    """
    Fetch ordered list of syllabus topics for an exam.
    Results ordered by priority (HIGH first) then difficulty (easiest first).
    NEVER ask the LLM to name topics; always use this tool.

    Args:
        exam_id: UUID string of the exam
        subject: Optional filter e.g. "Quantitative Aptitude"
        min_priority: Optional "HIGH" or "MED" to filter out LOW priority topics

    Returns:
        List of dicts: [{ topic_id, topic_name, subject, difficulty, priority,
                          estimated_hours, prerequisite_ids, subtopics }]
    """
    pool = await get_pool()
    query = """
        SELECT id::text AS topic_id, topic_name, subject, difficulty, priority,
               estimated_hours, prerequisite_ids::text[], subtopics
        FROM syllabus_topics
        WHERE exam_id = $1::uuid
    """
    params: list[object] = [exam_id]
    if subject:
        query += f" AND subject = ${len(params) + 1}"
        params.append(subject)
    if min_priority:
        priority_order = {"HIGH": 1, "MED": 2, "LOW": 3}
        allowed = [
            priority
            for priority, value in priority_order.items()
            if value <= priority_order.get(min_priority, 3)
        ]
        query += f" AND priority = ANY(${len(params) + 1})"
        params.append(allowed)
    query += """
        ORDER BY CASE priority WHEN 'HIGH' THEN 1 WHEN 'MED' THEN 2 ELSE 3 END,
                 difficulty ASC
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(row) for row in rows]


@tool
async def fetch_weak_areas(user_id: str, limit: int = 5) -> list[dict]:
    """
    Fetch user's weakest topics from the weak_areas cache table.
    Returns empty list for new users (no quiz history yet).
    DO NOT query user_performance directly; always use this table.

    Args:
        user_id: UUID string
        limit: Max number of weak topics to return (default 5)

    Returns:
        List of dicts: [{ topic_id, topic_name, weakness_score, rank,
                          recommended_extra_mins }]
        Ordered by rank ASC (rank 1 = weakest).
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT wa.topic_id::text, st.topic_name, wa.weakness_score,
                   wa.rank, wa.recommended_extra_mins
            FROM weak_areas wa
            JOIN syllabus_topics st ON st.id = wa.topic_id
            WHERE wa.user_id = $1::uuid
            ORDER BY wa.rank ASC
            LIMIT $2
            """,
            user_id,
            limit,
        )
    return [dict(row) for row in rows]


@tool
async def get_topic_details(topic_id: str) -> dict:
    """
    Fetch full topic details including subtopics and difficulty.
    Teacher Agent uses this to understand what needs to be taught.

    Args:
        topic_id: UUID string of the syllabus topic

    Returns:
        dict: { topic_id, topic_name, subject, subtopics, difficulty, priority,
                estimated_hours, prerequisite_ids }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id::text AS topic_id, topic_name, subject, subtopics,
                   difficulty, priority, estimated_hours, prerequisite_ids::text[]
            FROM syllabus_topics
            WHERE id = $1::uuid
            """,
            topic_id,
        )
    if not row:
        raise ValueError(f"Topic {topic_id} not found")
    return dict(row)


@tool
async def fetch_plan_day(plan_day_id: str) -> dict:
    """
    Load a specific study plan day's details including topic and revision list.

    Args:
        plan_day_id: UUID string of the study_plan_days row

    Returns:
        dict: { plan_day_id, day_number, scheduled_date, topic_id, topic_name,
                revision_topic_ids, allocated_minutes, status }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT spd.id::text AS plan_day_id, spd.day_number,
                   spd.scheduled_date::text, spd.topic_id::text,
                   st.topic_name, spd.revision_topic_ids::text[],
                   spd.allocated_minutes, spd.status
            FROM study_plan_days spd
            JOIN syllabus_topics st ON st.id = spd.topic_id
            WHERE spd.id = $1::uuid
            """,
            plan_day_id,
        )
    if not row:
        raise ValueError(f"Plan day {plan_day_id} not found")
    return dict(row)


@tool
async def fetch_teaching_history(user_id: str, topic_id: str) -> dict:
    """
    Check if a topic has been taught before; return last session summary.
    Teacher Agent uses this to avoid repeating content and build on prior teaching.

    Args:
        user_id: UUID string
        topic_id: UUID string

    Returns:
        dict: { previously_taught: bool, last_summary: str | None,
                last_taught_at: str | None, session_count: int }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT COUNT(*)::int AS session_count,
                   MAX(taught_at)::text AS last_taught_at,
                   (SELECT content_summary
                    FROM teaching_logs
                    WHERE user_id = $1::uuid AND topic_id = $2::uuid
                    ORDER BY taught_at DESC
                    LIMIT 1) AS last_summary
            FROM teaching_logs
            WHERE user_id = $1::uuid AND topic_id = $2::uuid
            """,
            user_id,
            topic_id,
        )
    return {
        "previously_taught": row["session_count"] > 0,
        "last_summary": row["last_summary"],
        "last_taught_at": row["last_taught_at"],
        "session_count": row["session_count"],
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
    """
    Persist a teaching session log with LLM reasoning trace for audit.

    Args:
        plan_day_id: UUID of study_plan_days row
        user_id: UUID string
        topic_id: UUID string of primary topic taught
        content_summary: LLM-generated plain-text summary of what was covered
        revision_covered: List of topic UUIDs revised in this session
        llm_trace: ReAct trace dict {thought, action, observation} for debugging
        duration_mins: Actual teaching time in minutes

    Returns:
        dict: { log_id: str }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        log_id = await conn.fetchval(
            """
            INSERT INTO teaching_logs
                (plan_day_id, user_id, topic_id, content_summary,
                 revision_covered, llm_trace, duration_mins)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4,
                    $5::uuid[], $6::jsonb, $7)
            RETURNING id::text
            """,
            plan_day_id,
            user_id,
            topic_id,
            content_summary,
            revision_covered,
            json.dumps(llm_trace),
            duration_mins,
        )
    return {"log_id": log_id}


@tool
async def mark_day_taught(plan_day_id: str) -> dict:
    """
    Mark a study plan day as taught. This is the FINAL action of every Teacher Agent run.
    Safe to retry; idempotent (updates to same state if already taught).

    Args:
        plan_day_id: UUID string

    Returns:
        dict: { status: 'taught', taught_at: str }
    """
    pool = await get_pool()
    now = datetime.now(UTC)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE study_plan_days
            SET status = 'taught', taught_at = $1
            WHERE id = $2::uuid
            """,
            now,
            plan_day_id,
        )
    return {"status": "taught", "taught_at": now.isoformat()}


@tool
async def store_quiz_attempt(
    user_id: str,
    topic_id: str,
    questions: list[dict],
    plan_day_id: str | None = None,
    template_id: str | None = None,
) -> dict:
    """
    Persist a quiz attempt row BEFORE the user begins answering.
    This enables timeout recovery (submitted_at remains NULL until submit).

    Args:
        user_id: UUID string
        topic_id: UUID string
        questions: List of {question_text, options: [str x4], correct_index: int, explanation: str}
        plan_day_id: Optional UUID; NULL for standalone quizzes
        template_id: Optional UUID of template used

    Returns:
        dict: { attempt_id: str }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        attempt_id = await conn.fetchval(
            """
            INSERT INTO quiz_attempts
                (user_id, topic_id, plan_day_id, template_id,
                 questions, total_questions)
            VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::jsonb, $6)
            RETURNING id::text
            """,
            user_id,
            topic_id,
            plan_day_id,
            template_id,
            json.dumps(questions),
            len(questions),
        )
    return {"attempt_id": attempt_id}


@tool
async def submit_quiz_attempt(
    attempt_id: str,
    user_answers: list[int],
    time_taken_secs: int,
) -> dict:
    """
    Score a quiz attempt. Scoring is done SERVER-SIDE; never trust client score.
    Updates submitted_at, score, user_answers in DB.

    Args:
        attempt_id: UUID string
        user_answers: List of chosen option indices (int), same length as questions
        time_taken_secs: Total time user took

    Returns:
        dict: { score: int, total: int, accuracy: float,
                per_question_result: [bool] }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT questions, total_questions FROM quiz_attempts WHERE id = $1::uuid",
            attempt_id,
        )
        if not row:
            raise ValueError(f"Attempt {attempt_id} not found")

        questions = row["questions"]
        if isinstance(questions, str):
            questions = json.loads(questions)

        results = [
            user_answer == question["correct_index"]
            for user_answer, question in zip(user_answers, questions)
        ]
        total = len(questions)
        score = sum(results)
        accuracy = round(score * 100.0 / total, 2) if total else 0.0

        await conn.execute(
            """
            UPDATE quiz_attempts
            SET user_answers = $1::jsonb,
                score = $2,
                time_taken_secs = $3,
                submitted_at = now()
            WHERE id = $4::uuid
            """,
            json.dumps(user_answers),
            score,
            time_taken_secs,
            attempt_id,
        )
    return {
        "score": score,
        "total": total,
        "accuracy": accuracy,
        "per_question_result": results,
    }


@tool
async def update_user_performance(
    user_id: str,
    topic_id: str,
    new_correct: int,
    new_attempts: int,
    avg_time_secs: float,
) -> dict:
    """
    Upsert user performance stats after a quiz. ALWAYS call this after submit_quiz_attempt.
    Uses INSERT ... ON CONFLICT DO UPDATE for idempotency.

    Args:
        user_id: UUID string
        topic_id: UUID string
        new_correct: Number of correct answers in this attempt
        new_attempts: Total questions attempted in this attempt
        avg_time_secs: Average seconds per question in this attempt

    Returns:
        dict: { updated_accuracy: float, new_weakness_score: float }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                INSERT INTO user_performance (user_id, topic_id, attempts, correct, avg_time_secs)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5)
                ON CONFLICT (user_id, topic_id) DO UPDATE
                SET attempts = user_performance.attempts + EXCLUDED.attempts,
                    correct = user_performance.correct + EXCLUDED.correct,
                    avg_time_secs = (user_performance.avg_time_secs + EXCLUDED.avg_time_secs) / 2,
                    last_attempted = now()
                RETURNING accuracy, attempts, correct, last_attempted
                """,
                user_id,
                topic_id,
                new_attempts,
                new_correct,
                avg_time_secs,
            )

            accuracy = float(row["accuracy"] or 0)
            last_attempted = row["last_attempted"]
            if last_attempted.tzinfo is None:
                last_attempted = last_attempted.replace(tzinfo=UTC)
            days_since = (datetime.now(UTC) - last_attempted).days
            recency_weight = max(0.0, 1.0 - days_since / 14.0)
            weakness_score = round((1 - accuracy / 100) * 70 + recency_weight * 30, 2)

            await conn.execute(
                """
                UPDATE user_performance
                SET weakness_score = $1
                WHERE user_id = $2::uuid AND topic_id = $3::uuid
                """,
                weakness_score,
                user_id,
                topic_id,
            )
    return {"updated_accuracy": accuracy, "new_weakness_score": weakness_score}


@tool
async def refresh_weak_areas(user_id: str) -> dict:
    """
    Rebuild the weak_areas cache table for a user after performance update.
    Ranks all topics by weakness_score DESC.
    Recommended extra mins = 20 if weakness_score >= 60, else 0.

    Args:
        user_id: UUID string

    Returns:
        dict: { refreshed_count: int, top_weak_topic: str | None }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM weak_areas WHERE user_id = $1::uuid", user_id)
            rows = await conn.fetch(
                """
                INSERT INTO weak_areas
                    (user_id, topic_id, weakness_score, rank, recommended_extra_mins)
                SELECT up.user_id,
                       up.topic_id,
                       up.weakness_score,
                       ROW_NUMBER() OVER (ORDER BY up.weakness_score DESC)::smallint AS rank,
                       CASE WHEN up.weakness_score >= 60 THEN 20 ELSE 0 END
                           AS recommended_extra_mins
                FROM user_performance up
                WHERE up.user_id = $1::uuid
                RETURNING topic_id::text
                """,
                user_id,
            )
            top = await conn.fetchval(
                """
                SELECT st.topic_name
                FROM weak_areas wa
                JOIN syllabus_topics st ON st.id = wa.topic_id
                WHERE wa.user_id = $1::uuid AND wa.rank = 1
                """,
                user_id,
            )
    return {"refreshed_count": len(rows), "top_weak_topic": top}


@tool
async def flag_replan(
    user_id: str,
    reason: str,
    affected_topic_ids: list[str],
) -> dict:
    """
    Write a replan flag into the active study_plan's meta JSONB.
    Planner checks this field on next plan creation or daily cron.
    Triggered when accuracy < 40% for 2 consecutive quiz sessions on a topic.

    Args:
        user_id: UUID string
        reason: Human-readable reason e.g. "accuracy < 40% for 2 sessions on Percentage"
        affected_topic_ids: List of topic UUID strings that need rescheduling

    Returns:
        dict: { replan_scheduled: bool, plan_id: str | None }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        plan_id = await conn.fetchval(
            """
            SELECT id::text
            FROM study_plans
            WHERE user_id = $1::uuid AND status = 'active'
            LIMIT 1
            """,
            user_id,
        )
        if not plan_id:
            return {"replan_scheduled": False, "plan_id": None}

        await conn.execute(
            """
            UPDATE study_plans
            SET meta = meta || $1::jsonb
            WHERE id = $2::uuid
            """,
            json.dumps(
                {
                    "replan_flag": True,
                    "replan_reason": reason,
                    "affected_topics": affected_topic_ids,
                    "flagged_at": datetime.now(UTC).isoformat(),
                }
            ),
            plan_id,
        )
    return {"replan_scheduled": True, "plan_id": plan_id}


@tool
async def compute_topic_order(
    topics: list[dict],
    weak_areas: list[dict],
    duration_days: int,
) -> dict:
    """
    Compute a day-by-day topic schedule respecting prerequisites and weakness weights.
    Weak topics (weakness_score >= 60) get 1.4x time allocation.
    Day N includes 15-min revision of Day N-2's topic in revision_ids.
    Daily budget = 90 minutes.

    Args:
        topics: List from get_exam_syllabus; [{topic_id, topic_name, difficulty,
                priority, estimated_hours, prerequisite_ids}]
        weak_areas: List from fetch_weak_areas; [{topic_id, weakness_score}]
        duration_days: Number of days in the plan

    Returns:
        dict: {
            ordered_plan: [
                { day: int, topic_id: str, topic_name: str,
                  revision_ids: [str], allocated_mins: int }
            ]
        }
    """
    daily_minutes = 90
    revision_minutes = 15
    weak_multiplier = 1.4

    weak_map = {weak["topic_id"]: weak["weakness_score"] for weak in weak_areas}
    topic_by_id = {topic["topic_id"]: topic for topic in topics}
    dep_count = {topic["topic_id"]: 0 for topic in topics}
    dependents: defaultdict[str, list[str]] = defaultdict(list)
    for topic in topics:
        for prereq in topic.get("prerequisite_ids") or []:
            if prereq in dep_count:
                dep_count[topic["topic_id"]] += 1
                dependents[prereq].append(topic["topic_id"])

    queue = deque([topic for topic in topics if dep_count[topic["topic_id"]] == 0])
    priority_val = {"HIGH": 0, "MED": 1, "LOW": 2}
    ordered_topics = []

    while queue:
        topic = min(
            queue,
            key=lambda item: (priority_val.get(item["priority"], 2), item["difficulty"]),
        )
        queue.remove(topic)
        ordered_topics.append(topic)
        for dep_id in dependents[topic["topic_id"]]:
            dep_count[dep_id] -= 1
            if dep_count[dep_id] == 0:
                queue.append(topic_by_id[dep_id])

    plan = []
    topic_index = 0
    for day_number in range(1, duration_days + 1):
        budget = daily_minutes
        revision_ids = []

        if day_number >= 3 and len(plan) >= 2:
            previous_topic_id = plan[day_number - 3]["topic_id"]
            if previous_topic_id:
                revision_ids = [previous_topic_id]
            budget -= revision_minutes

        if topic_index >= len(ordered_topics):
            plan.append(
                {
                    "day": day_number,
                    "topic_id": None,
                    "topic_name": "Revision Day",
                    "revision_ids": revision_ids,
                    "allocated_mins": daily_minutes,
                }
            )
            continue

        topic = ordered_topics[topic_index]
        is_weak = weak_map.get(topic["topic_id"], 0) >= 60
        allocation = min(budget, int(budget * weak_multiplier) if is_weak else budget)
        plan.append(
            {
                "day": day_number,
                "topic_id": topic["topic_id"],
                "topic_name": topic["topic_name"],
                "revision_ids": revision_ids,
                "allocated_mins": allocation,
            }
        )
        topic_index += 1

    return {"ordered_plan": plan}


@tool
async def create_study_plan(
    user_id: str,
    exam_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    """
    Insert a new study_plans row. Marks any previous active plan for the user as abandoned.

    Args:
        user_id: UUID string
        exam_id: UUID string
        start_date: ISO date string "YYYY-MM-DD"
        end_date: ISO date string "YYYY-MM-DD"

    Returns:
        dict: { plan_id: str, planner_version: int }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                UPDATE study_plans
                SET status = 'abandoned'
                WHERE user_id = $1::uuid AND status = 'active'
                """,
                user_id,
            )
            plan_id = await conn.fetchval(
                """
                INSERT INTO study_plans (user_id, exam_id, start_date, end_date)
                VALUES ($1::uuid, $2::uuid, $3::date, $4::date)
                RETURNING id::text
                """,
                user_id,
                exam_id,
                start_date,
                end_date,
            )
    return {"plan_id": plan_id, "planner_version": 1}


@tool
async def create_plan_days(
    plan_id: str,
    ordered_plan: list[dict],
    start_date: str,
) -> dict:
    """
    Bulk-insert all study_plan_days rows for a plan.
    ordered_plan comes directly from compute_topic_order output.

    Args:
        plan_id: UUID string (from create_study_plan)
        ordered_plan: List from compute_topic_order: [{day, topic_id, revision_ids, allocated_mins}]
        start_date: ISO date "YYYY-MM-DD"; day 1 maps to this date

    Returns:
        dict: { days_created: int }
    """
    base = date.fromisoformat(start_date)
    pool = await get_pool()

    rows = [
        (
            plan_id,
            item["day"],
            (base + timedelta(days=item["day"] - 1)).isoformat(),
            item.get("topic_id"),
            item.get("revision_ids", []),
            item["allocated_mins"],
        )
        for item in ordered_plan
        if item.get("topic_id")
    ]

    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO study_plan_days
                (plan_id, day_number, scheduled_date, topic_id,
                 revision_topic_ids, allocated_minutes)
            VALUES ($1::uuid, $2, $3::date, $4::uuid, $5::uuid[], $6)
            """,
            rows,
        )
    return {"days_created": len(rows)}
