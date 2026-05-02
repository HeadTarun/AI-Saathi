"""
Quiz generation tools.
RULE: Puzzles/Series/Direction Sense/Coding-Decoding MUST use templates.
      Only Arithmetic/DI may allow LLM to vary numbers within template structure.
"""

import ast
import json
import operator
import random

from langchain_core.tools import tool

from db import get_pool

MANDATORY_TEMPLATE_TYPES = {
    "Puzzles",
    "Seating Arrangement",
    "Direction Sense",
    "Coding-Decoding",
    "Series",
    "Blood Relations",
}

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _json_value(value: object) -> object:
    if isinstance(value, str):
        return json.loads(value)
    return value


def _safe_eval_numeric(expression: str) -> float:
    node = ast.parse(expression, mode="eval")

    def evaluate(current: ast.AST) -> float:
        if isinstance(current, ast.Expression):
            return evaluate(current.body)
        if isinstance(current, ast.Constant) and isinstance(current.value, int | float):
            return current.value
        if isinstance(current, ast.BinOp) and type(current.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(current.op)](
                evaluate(current.left),
                evaluate(current.right),
            )
        if isinstance(current, ast.UnaryOp) and type(current.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(current.op)](evaluate(current.operand))
        raise ValueError(f"Unsupported formula expression: {expression}")

    return float(evaluate(node))


@tool
async def get_quiz_templates(
    topic_id: str,
    difficulty: int | None = None,
    template_type: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Fetch quiz templates for a topic. MANDATORY first call for puzzle/series topics.
    Check topic_name against MANDATORY_TEMPLATE_TYPES before deciding to free-generate.

    Args:
        topic_id: UUID string
        difficulty: Optional int 1-5
        template_type: Optional filter: 'mcq' | 'fill' | 'match' | 'arrange' | 'puzzle_grid'
        limit: Max templates to return (default 10)

    Returns:
        List of dicts: [{ template_id, template_type, difficulty,
                          template_body, answer_key }]
        Returns empty list if no templates exist (caller decides to free-generate for non-mandatory).
    """
    pool = await get_pool()
    query = """
        SELECT id::text AS template_id, template_type, difficulty,
               template_body, answer_key
        FROM quiz_templates
        WHERE topic_id = $1::uuid AND is_active = true
    """
    params: list[object] = [topic_id]
    if difficulty is not None:
        query += f" AND difficulty = ${len(params) + 1}"
        params.append(difficulty)
    if template_type:
        query += f" AND template_type = ${len(params) + 1}"
        params.append(template_type)
    query += f" ORDER BY usage_count ASC LIMIT ${len(params) + 1}"
    params.append(limit)

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
        if rows:
            ids = [row["template_id"] for row in rows]
            await conn.execute(
                """
                UPDATE quiz_templates
                SET usage_count = usage_count + 1
                WHERE id = ANY($1::uuid[])
                """,
                ids,
            )
    return [dict(row) for row in rows]


@tool
async def generate_quiz_from_template(
    template_id: str,
    num_questions: int,
    difficulty: int,
) -> dict:
    """
    Instantiate a quiz template with randomized valid parameters.
    For numeric templates (Arithmetic): randomize slot values within valid ranges.
    For puzzle/grid templates: use template_body as-is (no LLM involved).

    Args:
        template_id: UUID string of quiz_templates row
        num_questions: Number of questions to generate (cap at template capacity)
        difficulty: Target difficulty 1-5 (used to scale numeric slot ranges)

    Returns:
        dict: {
            questions: [
                {
                    question_text: str,
                    options: [str, str, str, str],
                    correct_index: int,
                    explanation: str,
                }
            ]
        }
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT template_type, template_body, answer_key
            FROM quiz_templates
            WHERE id = $1::uuid
            """,
            template_id,
        )
    if not row:
        raise ValueError(f"Template {template_id} not found")

    body = _json_value(row["template_body"])
    answer_key = _json_value(row["answer_key"])
    template_type = row["template_type"]
    questions = []

    if template_type == "mcq":
        max_questions = min(num_questions, body.get("max_questions", num_questions))
        for _ in range(max_questions):
            slot_values = {}
            for slot in body.get("slots", []):
                lo, hi = slot["range"][0], slot["range"][1]
                scale = 1 + (difficulty - 1) * 0.3
                lo_scaled = int(lo * scale)
                hi_scaled = int(hi * scale)
                slot_values[slot["name"]] = random.randint(lo_scaled, hi_scaled)

            question_text = body["question_template"].format(**slot_values)
            formula = answer_key["formula"].format(**slot_values)
            correct_answer = _safe_eval_numeric(formula)
            correct_text = str(round(correct_answer, 2))

            distractors = [str(round(correct_answer * ratio, 1)) for ratio in [0.75, 1.25, 1.5]]
            options = [correct_text] + distractors[:3]
            random.shuffle(options)
            correct_index = options.index(correct_text)

            questions.append(
                {
                    "question_text": question_text,
                    "options": options,
                    "correct_index": correct_index,
                    "explanation": body.get("explanation_template", "").format(
                        answer=correct_text,
                        **slot_values,
                    ),
                }
            )
    elif template_type == "puzzle_grid":
        for item in body.get("questions", [])[:num_questions]:
            questions.append(
                {
                    "question_text": item["q"],
                    "options": item["options"],
                    "correct_index": item["correct_index"],
                    "explanation": item.get("explanation", ""),
                }
            )
    else:
        for item in body.get("questions", [])[:num_questions]:
            questions.append(
                {
                    "question_text": item.get("q", ""),
                    "options": item.get("options", []),
                    "correct_index": item.get("correct_index", 0),
                    "explanation": item.get("explanation", ""),
                }
            )

    return {"questions": questions}
