"""
Progress Analyzer Agent - AI Study Companion
============================================
Inputs: user_id, quiz_attempt_id
Outputs: Updated user_performance + weak_areas rows; optional replan flag

ReAct loop:
  load_quiz_attempt (via DB direct - not a separate tool, logic inline)
  -> update_user_performance
  -> refresh_weak_areas
  -> [check consecutive failures]
  -> flag_replan (if triggered)

This agent has minimal LLM involvement - it is mostly a deterministic data pipeline.
The LLM is used only to format the final progress summary for the API response.
"""

import json
import os
from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from src.db import get_pool
from src.tools import (
    fetch_weak_areas,
    flag_replan,
    refresh_weak_areas,
    update_user_performance,
)


class ProgressState(BaseModel):
    messages: Annotated[Sequence[BaseMessage], add_messages] = Field(default_factory=list)


def _get_llm():
    """Groq primary, ChatOllama fallback."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        from langchain_groq import ChatGroq

        return ChatGroq(model="llama3-70b-8192", temperature=0, api_key=groq_key)

    from langchain_ollama import ChatOllama

    return ChatOllama(
        model="phi3",
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    )


ANALYZER_TOOLS = [
    update_user_performance,
    refresh_weak_areas,
    flag_replan,
    fetch_weak_areas,
]


SYSTEM_PROMPT = """You are the Progress Analyzer for an AI Study Companion.

You run AFTER every quiz submission. Your job is deterministic - follow exact steps.

## MANDATORY TOOL SEQUENCE:
1. update_user_performance(user_id, topic_id, new_correct, new_attempts, avg_time_secs)
2. refresh_weak_areas(user_id)
3. fetch_weak_areas(user_id, limit=5) -> get updated weak topics for response
4. Check if flag_replan is needed using the REPLAN THRESHOLD below
5. If replan is needed: flag_replan(user_id, reason, affected_topic_ids)

## REPLAN THRESHOLD:
You will be told in the input message whether consecutive_failures >= 2 for this topic.
If consecutive_failures >= 2 AND current_accuracy < 40:
  -> Call flag_replan with:
    reason = "accuracy < 40% for 2 consecutive sessions on [topic_name]"
    affected_topic_ids = [topic_id]

## FINAL RESPONSE FORMAT:
Return ONLY this JSON object:
{
  "updated_accuracy": <float>,
  "new_weakness_score": <float>,
  "top_weak_topics": [
    { "topic_name": str, "weakness_score": float, "rank": int }
  ],
  "replan_triggered": <bool>
}

Do not add conversational text. Return only the JSON object.
"""


async def load_attempt_context(attempt_id: str) -> dict:
    """
    Load quiz attempt data and check consecutive failure count.
    Returns everything the Progress Analyzer needs as input.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        attempt = await conn.fetchrow(
            """
            SELECT qa.user_id::text,
                   qa.topic_id::text,
                   qa.score,
                   qa.total_questions,
                   qa.time_taken_secs,
                   st.topic_name,
                   ROUND(qa.score * 100.0 / NULLIF(qa.total_questions, 0), 2) AS accuracy
            FROM quiz_attempts qa
            JOIN syllabus_topics st ON st.id = qa.topic_id
            WHERE qa.id = $1::uuid
              AND qa.submitted_at IS NOT NULL
            """,
            attempt_id,
        )
        if not attempt:
            raise ValueError(f"Attempt {attempt_id} not found or not yet submitted")

        consecutive_failures = await conn.fetchval(
            """
            SELECT COUNT(*)::int
            FROM (
                SELECT score, total_questions
                FROM quiz_attempts
                WHERE user_id = $1::uuid
                  AND topic_id = $2::uuid
                  AND submitted_at IS NOT NULL
                ORDER BY submitted_at DESC
                LIMIT 2
            ) recent
            WHERE recent.total_questions > 0
              AND (recent.score * 100.0 / recent.total_questions) < 40
            """,
            attempt["user_id"],
            attempt["topic_id"],
        )

    avg_time = (attempt["time_taken_secs"] or 0) / max(attempt["total_questions"], 1)

    return {
        "user_id": attempt["user_id"],
        "topic_id": attempt["topic_id"],
        "topic_name": attempt["topic_name"],
        "new_correct": attempt["score"],
        "new_attempts": attempt["total_questions"],
        "avg_time_secs": round(avg_time, 2),
        "current_accuracy": float(attempt["accuracy"] or 0),
        "consecutive_failures": consecutive_failures,
    }


def build_progress_analyzer():
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(ANALYZER_TOOLS)

    def call_model(state: ProgressState) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state.messages]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: ProgressState) -> str:
        last = state.messages[-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    tool_node = ToolNode(ANALYZER_TOOLS)

    graph = StateGraph(ProgressState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


progress_analyzer = build_progress_analyzer()


def _parse_progress_json(content: str) -> dict:
    clean = content.strip()
    if clean.startswith("```"):
        clean = clean.split("```", 2)[1].strip()
        if clean.startswith("json"):
            clean = clean[4:].strip()
    return json.loads(clean)


async def run_progress_analysis(attempt_id: str) -> dict:
    """
    Full pipeline:
    1. Load attempt context from DB
    2. Build input message for the agent
    3. Run agent
    4. Return parsed JSON result

    API layer calls this function, not the agent directly.
    """
    ctx = await load_attempt_context(attempt_id)

    input_msg = HumanMessage(
        content=f"""
Analyze quiz performance:
- user_id: {ctx["user_id"]}
- topic_id: {ctx["topic_id"]}
- topic_name: {ctx["topic_name"]}
- new_correct: {ctx["new_correct"]}
- new_attempts: {ctx["new_attempts"]}
- avg_time_secs: {ctx["avg_time_secs"]}
- current_accuracy: {ctx["current_accuracy"]}
- consecutive_failures: {ctx["consecutive_failures"]}

If consecutive_failures >= 2 AND current_accuracy < 40, trigger flag_replan.
"""
    )

    result = await progress_analyzer.ainvoke({"messages": [input_msg]})
    last_msg = result["messages"][-1].content

    try:
        return _parse_progress_json(last_msg)
    except Exception:
        return {
            "updated_accuracy": ctx["current_accuracy"],
            "new_weakness_score": None,
            "top_weak_topics": [],
            "replan_triggered": False,
            "_raw": last_msg,
        }
