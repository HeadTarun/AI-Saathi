from __future__ import annotations

import uuid
from typing import Any, Literal, Protocol

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from agents.langgraph_state import StudyAgentInput, StudyAgentState
from agents.llm import get_llm
from agents.memory import (
    WorkflowMemory,
    get_default_workflow_memory,
    recent_messages_from_memory,
    sanitize_recent_messages,
)
from agents.observability import redact_text, safe_log, timed_call
from agents.safety import (
    check_rate_limit,
    retry_transient,
    sanitize_tool_payload,
    with_timeout,
)
from agents.tools import STUDY_CORE_TOOL_MAP


SupervisorAgent = Literal["planner", "teacher", "quiz", "progress", "replan", "general_help"]


class SupervisorDecision(BaseModel):
    """Structured supervisor output used to route the study graph."""

    agent: SupervisorAgent = Field(..., description="Specialized agent node to execute next.")
    task: str = Field(..., min_length=1, description="Specific study task to perform.")
    message: str = Field(..., min_length=1, description="Short user-facing status message.")
    tool_name: str | None = Field(None, description="LangChain tool name to call, if needed.")
    tool_input: dict[str, Any] = Field(default_factory=dict, description="Validated tool input.")


class StructuredSupervisor(Protocol):
    def invoke(self, input: Any, config: Any | None = None) -> SupervisorDecision | dict[str, Any]:
        ...


SUPERVISOR_SYSTEM_PROMPT = """You are the AI Study Companion supervisor.
Route the learner request to exactly one agent:
- planner: create a standard or custom study plan.
- teacher: teach a plan day or explain a topic.
- quiz: generate or submit a quiz.
- progress: fetch profile, active plan, or progress.
- replan: adjust remaining study days.
- general_help: answer lightweight study-help requests without a tool.

Return a structured decision. Prefer tools that already exist. Include user_id from context
when a tool needs it. If the request is missing required fields, choose general_help and
ask a concise clarification in message.
"""

AGENT_DEFAULT_TOOLS: dict[SupervisorAgent, str | None] = {
    "planner": "study_build_plan",
    "teacher": "study_teach_plan_day",
    "quiz": "study_generate_quiz",
    "progress": "study_get_progress",
    "replan": "study_replan_user",
    "general_help": None,
}

TOOL_AGENT_BY_NAME: dict[str, SupervisorAgent] = {
    "study_build_plan": "planner",
    "study_build_custom_rag_plan": "planner",
    "study_get_active_plan": "progress",
    "study_get_user_profile": "progress",
    "study_teach_plan_day": "teacher",
    "study_lesson_for_topic": "teacher",
    "study_generate_quiz": "quiz",
    "study_submit_quiz": "quiz",
    "study_get_progress": "progress",
    "study_replan_user": "replan",
    "study_rag_retrieve_content": "teacher",
}

ALLOWED_TOOL_NAMES = frozenset(TOOL_AGENT_BY_NAME)
LLM_TIMEOUT_SECONDS = 30.0
TOOL_TIMEOUT_SECONDS = 45.0


def build_study_graph(
    llm: Any | None = None,
    *,
    tools: dict[str, Any] | None = None,
    checkpointer: Any | None = None,
) -> Runnable:
    """Build the production LangGraph supervisor workflow.

    `llm` is injectable for deterministic tests. Production callers can omit it and the
    configured provider from `agents.llm` will be used.
    """
    tool_registry = tools or STUDY_CORE_TOOL_MAP
    tool_registry = {name: tool for name, tool in tool_registry.items() if name in ALLOWED_TOOL_NAMES}
    supervisor = _structured_supervisor(llm)

    def supervisor_node(state: StudyAgentState) -> dict[str, Any]:
        request_id = state["request_id"]
        user_id = state["user_id"]
        safe_log(
            "node_started",
            request_id=request_id,
            user_id=user_id,
            node="supervisor",
        )
        decision = timed_call(
            "llm_supervisor",
            lambda: _coerce_decision(
                with_timeout(
                    lambda: supervisor.invoke(
                        [
                            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
                            HumanMessage(
                                content=(
                                    f"user_id={state['user_id']}\n"
                                    f"request={state['user_query']}\n"
                                    f"context={state.get('metadata', {}).get('context', {})}\n"
                                    f"memory={state.get('metadata', {}).get('memory', {})}"
                                )
                            ),
                        ]
                    ),
                    timeout_seconds=LLM_TIMEOUT_SECONDS,
                    label="supervisor LLM call",
                )
            ),
            request_id=request_id,
            user_id=user_id,
            node="supervisor",
        )
        safe_log(
            "node_finished",
            request_id=request_id,
            user_id=user_id,
            node="supervisor",
            agent=decision.agent,
            task=decision.task,
        )
        return {
            "intent": _intent_for_agent(decision.agent, decision.task),
            "status": "running",
            "structured_output": decision.model_dump(),
            "metadata": _with_event(
                state,
                {
                    "node": "supervisor",
                    "agent": decision.agent,
                    "task": decision.task,
                    "tool_name": decision.tool_name,
                },
            ),
        }

    def planner_node(state: StudyAgentState) -> dict[str, Any]:
        return _run_tool_node(state, "planner", tool_registry)

    def teacher_node(state: StudyAgentState) -> dict[str, Any]:
        return _run_tool_node(state, "teacher", tool_registry)

    def quiz_node(state: StudyAgentState) -> dict[str, Any]:
        return _run_tool_node(state, "quiz", tool_registry)

    def progress_node(state: StudyAgentState) -> dict[str, Any]:
        return _run_tool_node(state, "progress", tool_registry)

    def replan_node(state: StudyAgentState) -> dict[str, Any]:
        return _run_tool_node(state, "replan", tool_registry)

    def general_help_node(state: StudyAgentState) -> dict[str, Any]:
        decision = _decision_from_state(state)
        data = {
            "answer": decision.message,
            "request": state["user_query"],
        }
        return {
            "status": "complete",
            "tool_results": [{"ok": True, "data": data}],
            "metadata": _with_event(
                state,
                {"node": "general_help", "agent": "general_help", "task": decision.task},
            ),
        }

    def final_response_node(state: StudyAgentState) -> dict[str, Any]:
        safe_log(
            "node_started",
            request_id=state["request_id"],
            user_id=state["user_id"],
            node="final_response",
        )
        decision = _decision_from_state(state)
        result = state.get("tool_results", [{}])[-1] if state.get("tool_results") else {}
        ok = bool(result.get("ok", True))
        data = result.get("data") if ok else {}
        tool_error = result.get("error") or {}
        message = decision.message if ok else _public_tool_error_message(tool_error)
        errors = state.get("errors", [])
        if not ok:
            errors = [*errors, _public_tool_error(tool_error)]
        final = {
            "agent": decision.agent,
            "task": decision.task,
            "message": message,
            "data": sanitize_tool_payload(data or {}) if ok else {"error": _public_tool_error(tool_error)},
            "events": state.get("metadata", {}).get("events", []),
        }
        response_message = AIMessage(content=message) if message else None
        memory = _memory_from_state(state, final, result, response_message=response_message)
        return {
            "status": "complete" if ok else "error",
            "final": final,
            "errors": errors,
            "messages": [response_message] if response_message else [],
            "metadata": {**(state.get("metadata") or {}), "memory": memory},
        }

    builder = StateGraph(StudyAgentState)
    builder.add_node("supervisor", supervisor_node)
    builder.add_node("planner", planner_node)
    builder.add_node("teacher", teacher_node)
    builder.add_node("quiz", quiz_node)
    builder.add_node("progress", progress_node)
    builder.add_node("replan", replan_node)
    builder.add_node("general_help", general_help_node)
    builder.add_node("final_response", final_response_node)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        _route_from_state,
        {
            "planner": "planner",
            "teacher": "teacher",
            "quiz": "quiz",
            "progress": "progress",
            "replan": "replan",
            "general_help": "general_help",
        },
    )
    for node_name in ("planner", "teacher", "quiz", "progress", "replan", "general_help"):
        builder.add_edge(node_name, "final_response")
    builder.add_edge("final_response", END)
    return builder.compile(checkpointer=checkpointer)


def run_study_graph(
    input_data: StudyAgentInput,
    *,
    llm: Any | None = None,
    tools: dict[str, Any] | None = None,
    memory: WorkflowMemory | None = None,
) -> dict[str, Any]:
    """Invoke the study graph and return the stable final response object."""
    workflow_memory = memory or get_default_workflow_memory()
    thread_key = workflow_memory.thread_key(input_data["user_id"], input_data.get("thread_id"))
    request_id = input_data.get("request_id") or f"req-{uuid.uuid4().hex[:12]}"
    check_rate_limit(input_data["user_id"])
    safe_log(
        "graph_run_started",
        request_id=request_id,
        user_id=input_data["user_id"],
        thread_key=thread_key,
    )
    graph = build_study_graph(
        llm=llm,
        tools=tools,
        checkpointer=workflow_memory.checkpointer(),
    )
    state = initial_state(
        {**input_data, "thread_id": thread_key, "request_id": request_id},
        prior_memory=workflow_memory.load(thread_key),
    )
    result = timed_call(
        "graph_run",
        lambda: graph.invoke(state, config=workflow_memory.config(thread_key)),
        request_id=request_id,
        user_id=input_data["user_id"],
        thread_key=thread_key,
    )
    return result["final"]


def stream_study_graph_events(
    input_data: StudyAgentInput,
    *,
    llm: Any | None = None,
    tools: dict[str, Any] | None = None,
    memory: WorkflowMemory | None = None,
):
    """Yield concise operational events from a real LangGraph execution."""
    workflow_memory = memory or get_default_workflow_memory()
    thread_key = workflow_memory.thread_key(input_data["user_id"], input_data.get("thread_id"))
    request_id = input_data.get("request_id") or f"req-{uuid.uuid4().hex[:12]}"
    try:
        check_rate_limit(input_data["user_id"])
    except Exception as exc:
        yield {
            "event": "error",
            "data": {
                "message": str(exc),
                "type": exc.__class__.__name__,
            },
        }
        return
    state = initial_state(
        {**input_data, "thread_id": thread_key, "request_id": request_id},
        prior_memory=workflow_memory.load(thread_key),
    )
    safe_log(
        "graph_stream_started",
        request_id=request_id,
        user_id=input_data["user_id"],
        thread_key=thread_key,
    )
    yield {
        "event": "graph_started",
        "data": {
            "message": "Study agent started.",
            "request_id": state["request_id"],
            "thread_id": state["thread_id"],
        },
    }
    try:
        graph = build_study_graph(
            llm=llm,
            tools=tools,
            checkpointer=workflow_memory.checkpointer(),
        )
        for update in graph.stream(
            state,
            config=workflow_memory.config(thread_key),
            stream_mode="updates",
        ):
            for node_name, node_update in update.items():
                yield from _events_from_node_update(node_name, node_update)
    except Exception as exc:
        yield {
            "event": "error",
            "data": {
                "message": str(exc),
                "type": exc.__class__.__name__,
            },
        }


def initial_state(
    input_data: StudyAgentInput,
    *,
    prior_memory: dict[str, Any] | None = None,
) -> StudyAgentState:
    request_id = input_data.get("request_id") or f"req-{uuid.uuid4().hex[:12]}"
    thread_id = input_data.get("thread_id") or f"study-{input_data['user_id']}"
    message = input_data["message"]
    memory = dict(prior_memory or {})
    messages = [*recent_messages_from_memory(memory), HumanMessage(content=message)]
    return {
        "messages": messages,
        "user_id": input_data["user_id"],
        "thread_id": thread_id,
        "request_id": request_id,
        "user_query": message,
        "intent": "general",
        "status": "pending",
        "auth": {},
        "profile": None,
        "active_plan": None,
        "plan_day": None,
        "topic": None,
        "retrieved_context": [],
        "tool_calls": [],
        "tool_results": [],
        "structured_output": None,
        "final": None,
        "errors": [],
        "retry_count": 0,
        "metadata": {
            "context": input_data.get("context", {}),
            "memory": memory,
            "events": [
                {
                    "node": "start",
                    "request_id": request_id,
                    "thread_id": thread_id,
                }
            ],
        },
    }


def _structured_supervisor(llm: Any | None) -> StructuredSupervisor:
    model = llm or get_llm()
    if hasattr(model, "with_structured_output"):
        return model.with_structured_output(SupervisorDecision)
    return model


def _coerce_decision(value: SupervisorDecision | dict[str, Any]) -> SupervisorDecision:
    if isinstance(value, SupervisorDecision):
        return value
    return SupervisorDecision.model_validate(value)


def _decision_from_state(state: StudyAgentState) -> SupervisorDecision:
    return _coerce_decision(state["structured_output"] or {})


def _route_from_state(state: StudyAgentState) -> SupervisorAgent:
    return _decision_from_state(state).agent


def _intent_for_agent(agent: SupervisorAgent, task: str) -> str:
    if agent == "planner":
        return "custom_plan" if "custom" in task.lower() else "plan"
    if agent == "teacher":
        return "teach"
    if agent == "quiz":
        return "submit_quiz" if "submit" in task.lower() else "quiz"
    if agent == "progress":
        return "profile" if "profile" in task.lower() else "progress"
    if agent == "replan":
        return "replan"
    return "general"


def _run_tool_node(
    state: StudyAgentState,
    agent: SupervisorAgent,
    tool_registry: dict[str, Any],
) -> dict[str, Any]:
    safe_log(
        "node_started",
        request_id=state["request_id"],
        user_id=state["user_id"],
        node=agent,
    )
    decision = _decision_from_state(state)
    tool_name = decision.tool_name or AGENT_DEFAULT_TOOLS[agent]
    if not tool_name:
        result = {"ok": True, "data": {"answer": decision.message}}
    elif TOOL_AGENT_BY_NAME.get(tool_name) != agent:
        result = {
            "ok": False,
            "error": {
                "type": "ToolRouteMismatch",
                "message": f"Tool {tool_name} cannot be used by agent {agent}",
            },
        }
    elif tool_name not in tool_registry:
        result = {
            "ok": False,
            "error": {
                "type": "ToolNotFound",
                "message": f"Tool is not registered: {tool_name}",
            },
        }
    else:
        tool_args = _inject_user_id(decision.tool_input, state)
        safe_log(
            "tool_call_started",
            request_id=state["request_id"],
            user_id=state["user_id"],
            agent=agent,
            tool_name=tool_name,
            tool_args=tool_args,
        )
        try:
            result = timed_call(
                "tool_call",
                lambda: retry_transient(
                    lambda: with_timeout(
                        lambda: tool_registry[tool_name].invoke(tool_args),
                        timeout_seconds=TOOL_TIMEOUT_SECONDS,
                        label=f"tool {tool_name}",
                    )
                ),
                request_id=state["request_id"],
                user_id=state["user_id"],
                agent=agent,
                tool_name=tool_name,
            )
        except Exception as exc:
            result = {
                "ok": False,
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                },
            }
        result = sanitize_tool_payload(result)
        safe_log(
            "tool_call_finished",
            request_id=state["request_id"],
            user_id=state["user_id"],
            agent=agent,
            tool_name=tool_name,
            ok=bool(result.get("ok")),
        )

    update = {
        "tool_results": [result],
        "tool_calls": [
            {
                "name": tool_name or "none",
                "args": _inject_user_id(decision.tool_input, state),
                "status": "complete" if result.get("ok") else "error",
                "error": None if result.get("ok") else (result.get("error") or {}).get("message"),
            }
        ],
        "metadata": _with_event(
            state,
            {
                "node": agent,
                "agent": agent,
                "task": decision.task,
                "tool_name": tool_name,
                "ok": bool(result.get("ok")),
            },
        ),
    }
    safe_log(
        "node_finished",
        request_id=state["request_id"],
        user_id=state["user_id"],
        node=agent,
        ok=bool(result.get("ok")),
    )
    return update


def _inject_user_id(tool_input: dict[str, Any], state: StudyAgentState) -> dict[str, Any]:
    args = dict(tool_input or {})
    args.setdefault("user_id", state["user_id"])
    return args


def _with_event(state: StudyAgentState, event: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(state.get("metadata") or {})
    events = [*metadata.get("events", []), event]
    metadata["events"] = events
    return metadata


def _memory_from_state(
    state: StudyAgentState,
    final: dict[str, Any],
    result: dict[str, Any],
    *,
    response_message: AIMessage | None = None,
) -> dict[str, Any]:
    prior = dict((state.get("metadata") or {}).get("memory") or {})
    data = final.get("data") if isinstance(final.get("data"), dict) else {}
    tool_call = (state.get("tool_calls") or [{}])[-1]
    messages = state.get("messages", [])
    if response_message:
        messages = [*messages, response_message]
    memory = {
        "latest_intent": state.get("intent"),
        "recent_messages": sanitize_recent_messages(messages),
        "active_plan_id": _first_present(
            data,
            prior,
            keys=("active_plan_id", "plan_id", "id", "updated_plan_id"),
            nested_keys=(("plan", "plan_id"), ("plan", "id"), ("active_plan", "plan_id"), ("active_plan", "id")),
        ),
        "active_plan_day_id": _first_present(
            data,
            tool_call.get("args") if isinstance(tool_call, dict) else {},
            prior,
            keys=("active_plan_day_id", "plan_day_id", "id"),
            nested_keys=(("plan_day", "id"),),
        ),
        "last_tool_results_summary": _summarize_tool_result(result),
    }
    return {key: value for key, value in memory.items() if value not in (None, "", [])}


def _first_present(
    *sources: dict[str, Any],
    keys: tuple[str, ...],
    nested_keys: tuple[tuple[str, str], ...] = (),
) -> Any:
    for source in sources:
        if not isinstance(source, dict):
            continue
        for parent, child in nested_keys:
            nested = source.get(parent)
            if isinstance(nested, dict) and nested.get(child):
                return nested[child]
        for key in keys:
            if source.get(key):
                return source[key]
    return None


def _summarize_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"ok": False, "type": "InvalidToolResult"}
    if not result.get("ok", True):
        error = result.get("error") or {}
        return {
            "ok": False,
            "type": error.get("type", "ToolError"),
            "message": str(error.get("message", ""))[:500],
        }
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    return {
        "ok": True,
        "keys": sorted(data.keys())[:20],
    }


def _public_tool_error(error: dict[str, Any]) -> dict[str, str]:
    return {
        "type": str(error.get("type") or "ToolError")[:120],
        "message": redact_text(str(error.get("message") or "Tool execution failed."), max_len=500),
    }


def _public_tool_error_message(error: dict[str, Any]) -> str:
    public = _public_tool_error(error)
    return f"{public['type']}: {public['message']}"


def _events_from_node_update(node_name: str, update: dict[str, Any]):
    if node_name == "supervisor":
        decision = _coerce_decision(update.get("structured_output") or {})
        yield {
            "event": "intent_detected",
            "data": {
                "agent": decision.agent,
                "task": decision.task,
                "message": decision.message,
            },
        }
        yield {
            "event": "node_finished",
            "data": {
                "node": "supervisor",
                "message": "Intent routed.",
            },
        }
        return

    if node_name in {"planner", "teacher", "quiz", "progress", "replan"}:
        tool_call = (update.get("tool_calls") or [{}])[-1]
        result = (update.get("tool_results") or [{}])[-1]
        tool_name = tool_call.get("name") or "unknown"
        yield {
            "event": "tool_started",
            "data": {
                "agent": node_name,
                "tool_name": tool_name,
                "message": f"Running {tool_name}.",
            },
        }
        yield {
            "event": "tool_finished",
            "data": {
                "agent": node_name,
                "tool_name": tool_name,
                "ok": bool(result.get("ok")),
                "message": "Tool completed." if result.get("ok") else "Tool failed.",
                "error": result.get("error"),
            },
        }
        yield {
            "event": "node_finished",
            "data": {
                "node": node_name,
                "message": f"{node_name} finished.",
            },
        }
        return

    if node_name == "general_help":
        yield {
            "event": "node_finished",
            "data": {
                "node": "general_help",
                "message": "General help finished.",
            },
        }
        return

    if node_name == "final_response":
        final = update.get("final") or {}
        yield {
            "event": "final_response",
            "data": final,
        }


__all__ = [
    "SupervisorDecision",
    "build_study_graph",
    "initial_state",
    "run_study_graph",
    "stream_study_graph_events",
]
