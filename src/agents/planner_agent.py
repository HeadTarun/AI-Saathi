"""
Planner Agent - AI Study Companion
==================================
Inputs: user_id, exam_id, duration_days, target_subjects (optional), user_level
Outputs: study_plans + study_plan_days rows written to DB; returns plan_id

ReAct loop:
  get_user_profile
  -> get_exam_syllabus
  -> fetch_weak_areas          (empty for new users)
  -> compute_topic_order       (priority + weakness weights)
  -> create_study_plan
  -> create_plan_days
  -> DONE

Constraints:
  - NEVER free-generate topic names
  - NEVER call other agents
  - All state in PostgreSQL
"""

import os
from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from src.tools import (
    compute_topic_order,
    create_plan_days,
    create_study_plan,
    fetch_weak_areas,
    get_exam_syllabus,
    get_user_profile,
)


class PlannerState(BaseModel):
    messages: Annotated[Sequence[BaseMessage], add_messages] = Field(default_factory=list)


def _get_llm():
    """Groq primary, ChatOllama fallback."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        from langchain_groq import ChatGroq

        return ChatGroq(
            model="llama3-70b-8192",
            temperature=0,
            api_key=groq_key,
        )

    from langchain_ollama import ChatOllama

    return ChatOllama(
        model="phi3",
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0,
    )


PLANNER_TOOLS = [
    get_user_profile,
    get_exam_syllabus,
    fetch_weak_areas,
    compute_topic_order,
    create_study_plan,
    create_plan_days,
]


SYSTEM_PROMPT = """You are the Planner Agent for an AI Study Companion for Indian competitive exams (SSC, Banking).

Your ONLY job is to create a personalized study plan by calling tools in the correct sequence.

## MANDATORY TOOL SEQUENCE (follow exactly):
1. get_user_profile(user_id) -> establish user context
2. get_exam_syllabus(exam_id) -> get ALL topics (never free-generate topics)
3. fetch_weak_areas(user_id) -> empty list for new users, that's fine
4. compute_topic_order(topics, weak_areas, duration_days) -> get ordered_plan
5. create_study_plan(user_id, exam_id, start_date, end_date) -> get plan_id
6. create_plan_days(plan_id, ordered_plan, start_date) -> persist days

## RULES:
- NEVER suggest or name topics yourself. ALL topics come from get_exam_syllabus.
- NEVER skip steps. Always call all 6 tools.
- After create_plan_days succeeds, respond with:
  "Plan created: plan_id={plan_id}, {duration_days} days starting {start_date}"
- Do not call other agents. Do not ask the user questions mid-run.
- If a tool fails, report the error and stop. Do not retry silently.

## WEAK TOPIC RULES:
- Topics with weakness_score >= 60 get 1.4x time allocation (handled by compute_topic_order).
- For new users (empty weak_areas), treat all topics equally.
"""


def build_planner_agent():
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(PLANNER_TOOLS)

    def call_model(state: PlannerState) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state.messages]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: PlannerState) -> str:
        last = state.messages[-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    tool_node = ToolNode(PLANNER_TOOLS)

    graph = StateGraph(PlannerState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


planner_agent = build_planner_agent()
