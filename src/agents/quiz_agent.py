"""
Quiz Agent - AI Study Companion
===============================
Inputs: user_id, topic_id, plan_day_id (optional), num_questions (default 10), difficulty (1-5)
Outputs: quiz_attempts row created; on submission -> scored + Progress Analyzer triggered

ReAct loop (GENERATE phase):
  fetch_weak_areas
  -> get_quiz_templates
  -> generate_quiz_from_template
  -> store_quiz_attempt
  -> return attempt_id + questions to user

ReAct loop (SUBMIT phase - separate invocation):
  submit_quiz_attempt
  -> [triggers Progress Analyzer via API]

Constraints:
  - Puzzle/Series/Direction topics MUST use templates; return an ERROR if none exist
  - Questions NEVER re-generated after store_quiz_attempt
  - Scoring is ALWAYS server-side (never trust client-submitted score)
"""

import os
from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

from tools import (
    fetch_weak_areas,
    generate_quiz_from_template,
    get_quiz_templates,
    get_topic_details,
    store_quiz_attempt,
    submit_quiz_attempt,
)

MANDATORY_TEMPLATE_TOPICS = {
    "Puzzles",
    "Seating Arrangement",
    "Direction Sense",
    "Coding-Decoding",
    "Series",
    "Blood Relations",
    "Order and Ranking",
    "Input-Output",
}


class QuizState(BaseModel):
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


QUIZ_TOOLS = [
    fetch_weak_areas,
    get_topic_details,
    get_quiz_templates,
    generate_quiz_from_template,
    store_quiz_attempt,
    submit_quiz_attempt,
]

MANDATORY_TOPICS_LIST = ", ".join(sorted(MANDATORY_TEMPLATE_TOPICS))

SYSTEM_PROMPT = f"""You are the Quiz Agent for an AI Study Companion.

Your job is to generate a quiz for a topic and persist it before the user starts answering.

## GENERATE PHASE - MANDATORY TOOL SEQUENCE:
1. get_topic_details(topic_id) -> check topic_name
2. fetch_weak_areas(user_id, limit=3) -> identify weak topics
3. get_quiz_templates(topic_id, difficulty) -> ALWAYS call this before generating questions
4. Decide based on topic_name and template availability
5. generate_quiz_from_template(template_id, num_questions, difficulty) -> get questions
6. store_quiz_attempt(user_id, topic_id, questions, plan_day_id) -> persist attempt
7. Return attempt_id and sanitized questions to the caller

## TEMPLATE DECISION RULES:
- If topic_name is in [{MANDATORY_TOPICS_LIST}]:
  - Templates are MANDATORY.
  - If get_quiz_templates returns an empty list, STOP and return exactly:
    "ERROR: No templates found for mandatory topic {{topic_name}}. Add templates before quizzing."
  - Do not free-generate questions for these topics.
- For all other topics:
  - If templates exist, prefer templates.
  - If no templates exist, you may generate MCQ questions yourself.
  - Free-generated questions must use this format:
    {{"question_text": str, "options": [str, str, str, str], "correct_index": int, "explanation": str}}
  - Generate exactly 4 options per question.
  - correct_index must be an integer from 0 to 3.
  - Base questions only on topic_name and subtopics from get_topic_details.
  - Never invent new topic names or subtopics.

## QUESTION DISTRIBUTION WHEN USING TEMPLATES:
- Prefer primary topic templates.
- If weak-topic templates are available, use them for up to 40% of the quiz.
- If weak topics have no templates, use 100% primary topic templates.
- The final stored questions list must contain exactly num_questions questions unless template capacity is lower.

## STORAGE AND SECURITY:
- Always call store_quiz_attempt before returning questions to the caller.
- quiz_attempts.questions is the single source of truth for scoring.
- Never re-generate questions after store_quiz_attempt.
- The stored questions must include question_text, options, correct_index, and explanation.
- The final response for generate phase must not expose correct_index or explanation.

## SUBMIT PHASE:
When called with attempt_id and user_answers:
1. submit_quiz_attempt(attempt_id, user_answers, time_taken_secs) -> score server-side
2. Return the tool result to the caller. The Progress Analyzer is triggered separately by the API.

## OUTPUT FORMAT AFTER store_quiz_attempt:
Return ONLY this JSON:
{{
  "attempt_id": "<uuid>",
  "questions": [
    {{"question_text": "<text>", "options": ["<a>", "<b>", "<c>", "<d>"]}}
  ],
  "total": <int>
}}
"""


def build_quiz_agent():
    llm = _get_llm()
    llm_with_tools = llm.bind_tools(QUIZ_TOOLS)

    def call_model(state: QuizState) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT), *state.messages]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: QuizState) -> str:
        last = state.messages[-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    tool_node = ToolNode(QUIZ_TOOLS)

    graph = StateGraph(QuizState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", tool_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


quiz_agent = build_quiz_agent()
