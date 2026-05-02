"""
Teacher Agent - AI Study Companion
==================================
Inputs: plan_day_id, user_id
Outputs: teaching_log row written; study_plan_days.status -> 'taught'

ReAct loop:
  fetch_plan_day
  -> get_user_profile
  -> get_topic_details
  -> fetch_teaching_history
  -> rag_retrieve_content
  -> [LLM generates lesson]
  -> store_teaching_log
  -> mark_day_taught

Constraints:
  - MUST call rag_retrieve_content before generating any lesson content
  - Lesson content MUST be grounded in RAG results
  - Revision topics use prior teaching_log summaries as context
  - mark_day_taught MUST be the final tool call
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
    fetch_plan_day,
    fetch_teaching_history,
    fetch_weak_areas,
    get_topic_details,
    get_user_profile,
    mark_day_taught,
    rag_retrieve_content,
    store_teaching_log,
)


class TeacherState(BaseModel):
    messages: Annotated[Sequence[BaseMessage], add_messages] = Field(default_factory=list)


def _get_llm():
    """Groq primary, ChatOllama fallback."""
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        from langchain_groq import ChatGroq

        return ChatGroq(
            model="llama3-70b-8192",
            temperature=0.3,
            api_key=groq_key,
        )

    from langchain_ollama import ChatOllama

    return ChatOllama(
        model="phi3",
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
        temperature=0.3,
    )


TEACHER_TOOLS = [
    fetch_plan_day,
    get_user_profile,
    get_topic_details,
    fetch_teaching_history,
    rag_retrieve_content,
    fetch_weak_areas,
    store_teaching_log,
    mark_day_taught,
]


SYSTEM_PROMPT = """You are the Teacher Agent for an AI Study Companion for Indian competitive exams (SSC CGL, SBI PO).

Your job is to teach today's topic to the user in a clear, structured manner adapted to their level.

## MANDATORY TOOL SEQUENCE:
1. fetch_plan_day(plan_day_id) -> get today's topic + revision list
2. get_user_profile(user_id) -> get user level (beginner/intermediate/advanced)
3. get_topic_details(topic_id) -> get subtopics to cover
4. fetch_teaching_history(user_id, topic_id) -> check if taught before
5. rag_retrieve_content(query, topic_id) -> get grounded content (MANDATORY before generating lesson)
6. Generate lesson based on RAG results
7. For each revision_topic_id: rag_retrieve_content(query, revision_topic_id) -> brief revision content
8. store_teaching_log(...) -> persist session
9. mark_day_taught(plan_day_id) -> ALWAYS the final tool call

## LESSON GENERATION RULES:
- ALWAYS base lesson on rag_retrieve_content results. Do not free-generate concepts.
- Adapt depth to user level:
  - beginner: Simple language, many examples, no jargon, define every term
  - intermediate: Standard explanation, 1-2 examples, introduce shortcuts
  - advanced: Concise, shortcut-focused, assume formula knowledge
- Structure every lesson as:
  1. "What is [Topic]?" - 2-3 sentence definition grounded in RAG
  2. "Key Concepts" - bullet points from subtopics
  3. "Worked Example" - one step-by-step example
  4. "Common Mistakes" - 2-3 pitfalls for this topic
  5. "Quick Formula/Trick" - 1 memory shortcut
- Revision topics: Cover in 3-4 lines using prior content_summary as refresh. Prefix with "📚 Quick Revision: [Topic Name]"

## CONTENT_SUMMARY for store_teaching_log:
Write a 3-5 sentence plain text summary of what was taught.
This summary is used in future sessions as revision context. Make it factual, not conversational.

## LLM_TRACE for store_teaching_log:
Populate llm_trace with a compact JSON object containing:
- topic_id
- plan_day_id
- rag_chunks_used
- revision_topic_ids
- lesson_sections
- tool_sequence_observed

## RULES:
- NEVER skip rag_retrieve_content. Even if history exists, always retrieve fresh RAG content.
- NEVER call mark_day_taught before store_teaching_log.
- NEVER call another tool after mark_day_taught.
- NEVER generate new topic names. All topic references come from fetch_plan_day and get_topic_details.
- If rag_retrieve_content returns empty, use the subtopics array from get_topic_details as fallback content.
- Do not ask the user questions during teaching. Deliver the complete lesson.
"""


def build_teacher_agent():
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(TEACHER_TOOLS)

    def call_model(state: TeacherState) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state.messages]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: TeacherState) -> str:
        last = state.messages[-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    tool_node = ToolNode(TEACHER_TOOLS)

    graph = StateGraph(TeacherState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


teacher_agent = build_teacher_agent()
