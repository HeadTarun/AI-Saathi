from __future__ import annotations

import random

from langchain_core.tools import tool

from db import get_supabase


@tool
async def get_quiz_templates(
    topic_id: str,
    difficulty: int | None = None,
    template_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Fetch quiz templates from Supabase."""
    query = (
        get_supabase()
        .table("quiz_templates")
        .select("id,template_type,difficulty,template_body,answer_key")
        .eq("topic_id", topic_id)
        .eq("is_active", True)
        .limit(limit)
    )
    if difficulty is not None:
        query = query.eq("difficulty", difficulty)
    if template_type:
        query = query.eq("template_type", template_type)
    rows = query.execute().data or []
    return [
        {
            "template_id": row["id"],
            "template_type": row["template_type"],
            "difficulty": row["difficulty"],
            "template_body": row["template_body"],
            "answer_key": row["answer_key"],
        }
        for row in rows
    ]


@tool
async def generate_quiz_from_template(
    template_id: str,
    num_questions: int,
    difficulty: int,
) -> dict:
    """Generate quiz questions from a Supabase quiz template."""
    rows = (
        get_supabase()
        .table("quiz_templates")
        .select("template_body,answer_key")
        .eq("id", template_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        raise ValueError(f"Template {template_id} not found")
    body = rows[0].get("template_body") or {}
    questions = body.get("questions") or []
    if not questions:
        questions = [
            {
                "question_text": body.get("question_template", "Practice question"),
                "options": body.get("options", ["A", "B", "C", "D"]),
                "correct_index": int(body.get("correct_index", 0)),
                "explanation": body.get("explanation_template", ""),
            }
        ]
    selected = questions[: max(1, min(num_questions, len(questions)))]
    random.shuffle(selected)
    return {"questions": selected}
