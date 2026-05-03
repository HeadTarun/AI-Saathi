from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from typing import Any

import study_core


@dataclass
class AIMessage:
    content: str

    def pretty_print(self) -> None:
        print(self.content)


@dataclass(frozen=True)
class AgentResult:
    agent: str
    task: str
    output: dict[str, Any]


class AgentError(RuntimeError):
    """Raised when a local agent cannot process a request."""


class BaseLocalAgent:
    name = "base"
    supported_tasks: frozenset[str] = frozenset()

    def process(self, payload: dict[str, Any], task: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def invoke(self, input: dict[str, Any], config: Any | None = None) -> dict[str, Any]:
        task, payload = _normalize_agent_input(input)
        output = self.process(payload, task)
        return _agent_response(self.name, task, output)

    async def ainvoke(self, input: dict[str, Any], config: Any | None = None) -> dict[str, Any]:
        return self.invoke(input=input, config=config)

    def stream(self, input: dict[str, Any], config: Any | None = None, **_: Any) -> Iterator[Any]:
        yield ("values", self.invoke(input=input, config=config))

    async def astream(
        self,
        input: dict[str, Any],
        config: Any | None = None,
        stream_mode: str | list[str] | None = None,
        **_: Any,
    ) -> AsyncIterator[Any]:
        yield ("values", self.invoke(input=input, config=config))


class PlannerAgent(BaseLocalAgent):
    name = "study-planner"
    supported_tasks = frozenset(
        {"build_plan", "build_custom_rag_plan", "get_plan", "get_profile", "list_topics", "list_exams", "replan"}
    )

    def process(self, payload: dict[str, Any], task: str | None = None) -> dict[str, Any]:
        if task == "build_plan":
            result = study_core.run_plan_workflow(
                user_id=_required(payload, "user_id"),
                exam_id_or_name=_required(payload, "exam_id_or_name", "exam_id", "exam"),
                duration_days=int(_required(payload, "duration_days", "duration")),
                start_date=payload.get("start_date"),
                name=str(payload.get("name") or "Learner"),
                level=str(payload.get("level") or "beginner"),
                email=str(payload.get("email") or "").strip() or None,
                user_goal=str(payload.get("user_goal") or "").strip() or None,
            )
            plan = result["plan"]
            return {
                "plan": plan,
                "plan_id": plan["plan_id"],
                "start_date": plan["start_date"],
                "end_date": plan["end_date"],
                "duration_days": plan["duration_days"],
                "workflow": result["workflow"],
                "message": (
                    f"Plan created: plan_id={plan['plan_id']}, "
                    f"{plan['duration_days']} days starting {plan['start_date']}"
                ),
            }
        if task == "build_custom_rag_plan":
            result = study_core.run_custom_rag_plan_workflow(
                user_id=_required(payload, "user_id"),
                duration_days=int(_required(payload, "duration_days", "duration")),
                start_date=payload.get("start_date"),
                name=str(payload.get("name") or "Learner"),
                level=str(payload.get("level") or "beginner"),
                email=str(payload.get("email") or "").strip() or None,
                user_goal=str(payload.get("user_goal") or "").strip() or None,
            )
            plan = result["plan"]
            return {
                "plan": plan,
                "plan_id": plan["plan_id"],
                "start_date": plan["start_date"],
                "end_date": plan["end_date"],
                "duration_days": plan["duration_days"],
                "workflow": result["workflow"],
                "message": (
                    f"Custom RAG plan created: plan_id={plan['plan_id']}, "
                    f"{plan['duration_days']} days starting {plan['start_date']}"
                ),
            }
        if task == "get_plan":
            plan = study_core.get_active_plan(_required(payload, "user_id"))
            if not plan:
                raise AgentError("No active plan found for user")
            return {"plan": plan}
        if task == "get_profile":
            return study_core.get_user_profile(_required(payload, "user_id"))
        if task == "list_topics":
            return {"topics": study_core.list_topics(_required(payload, "exam_id_or_name", "exam_id", "exam"))}
        if task == "list_exams":
            return {"exams": study_core.list_exams()}
        if task == "replan":
            return study_core.replan_user(_required(payload, "user_id"))
        raise AgentError(f"{self.name} cannot process task: {task}")


class TeacherAgent(BaseLocalAgent):
    name = "study-teacher"
    supported_tasks = frozenset({"teach_day", "lesson_for_topic"})

    def process(self, payload: dict[str, Any], task: str | None = None) -> dict[str, Any]:
        if task == "teach_day":
            return study_core.teach_plan_day(
                plan_day_id=_required(payload, "plan_day_id"),
                user_id=_required(payload, "user_id"),
            )
        if task == "lesson_for_topic":
            return {
                "lesson_content": study_core.lesson_for_topic(
                    topic_name=_required(payload, "topic_name"),
                    level=str(payload.get("level") or "beginner"),
                )
            }
        raise AgentError(f"{self.name} cannot process task: {task}")


class QuizAgent(BaseLocalAgent):
    name = "study-quiz"
    supported_tasks = frozenset({"generate_quiz", "submit_quiz"})

    def process(self, payload: dict[str, Any], task: str | None = None) -> dict[str, Any]:
        if task == "generate_quiz":
            return study_core.generate_quiz(
                user_id=_required(payload, "user_id"),
                topic_id=_required(payload, "topic_id"),
                num_questions=int(payload.get("num_questions") or 5),
                difficulty=int(payload.get("difficulty") or 3),
                plan_day_id=payload.get("plan_day_id"),
            )
        if task == "submit_quiz":
            answers = payload.get("user_answers")
            if not isinstance(answers, list):
                raise AgentError("user_answers must be a list")
            return study_core.submit_quiz(
                attempt_id=_required(payload, "attempt_id"),
                user_answers=answers,
                time_taken_secs=int(_required(payload, "time_taken_secs")),
            )
        raise AgentError(f"{self.name} cannot process task: {task}")


class ProgressAgent(BaseLocalAgent):
    name = "study-progress"
    supported_tasks = frozenset({"get_progress"})

    def process(self, payload: dict[str, Any], task: str | None = None) -> dict[str, Any]:
        if task == "get_progress":
            return study_core.get_progress(_required(payload, "user_id"))
        raise AgentError(f"{self.name} cannot process task: {task}")


class RouterAgent(BaseLocalAgent):
    name = "study-router"

    def __init__(self, task_agents: dict[str, BaseLocalAgent]) -> None:
        self.task_agents = task_agents

    @property
    def supported_tasks(self) -> frozenset[str]:
        tasks: set[str] = set()
        for agent in self.task_agents.values():
            tasks.update(agent.supported_tasks)
        return frozenset(tasks)

    def process(self, payload: dict[str, Any], task: str | None = None) -> dict[str, Any]:
        if not task:
            task = _infer_task_from_text(str(payload.get("message") or ""))
        agent = self._agent_for_task(task)
        output = agent.process(payload, task)
        return AgentResult(agent=agent.name, task=task, output=output).__dict__

    def _agent_for_task(self, task: str) -> BaseLocalAgent:
        for agent in self.task_agents.values():
            if task in agent.supported_tasks:
                return agent
        raise AgentError(f"No agent can process task: {task}")


def run_agent_task(router: RouterAgent, task: str, **payload: Any) -> dict[str, Any]:
    result = router.process(payload, task)
    output = result["output"]
    if not isinstance(output, dict):
        raise AgentError(f"Agent task {task} returned non-dict output")
    return output


def _normalize_agent_input(input_data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if "task" in input_data:
        payload = input_data.get("payload", {})
        if not isinstance(payload, dict):
            raise AgentError("payload must be a dictionary")
        return str(input_data["task"]), payload

    if "messages" in input_data:
        messages = input_data["messages"]
        if not messages:
            raise AgentError("messages cannot be empty")
        content = _message_content(messages[-1])
        return _infer_task_from_text(content), {"message": content}

    raise AgentError("Agent input must include either task/payload or messages")


def _message_content(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("content") or "")
    if hasattr(message, "content"):
        return str(message.content)
    return str(message)


def _infer_task_from_text(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("quiz", "question", "mcq")):
        return "generate_quiz"
    if any(word in lowered for word in ("teach", "lesson", "explain")):
        return "lesson_for_topic"
    if "progress" in lowered:
        return "get_progress"
    if "replan" in lowered or "re-plan" in lowered:
        return "replan"
    return "build_plan"


def _agent_response(agent_name: str, task: str, output: dict[str, Any]) -> dict[str, Any]:
    content = json.dumps(output, ensure_ascii=True, default=str)
    return {
        "messages": [AIMessage(content=content)],
        "agent": agent_name,
        "task": task,
        "output": output,
    }


def _required(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value
    joined = " or ".join(keys)
    raise AgentError(f"Missing required field: {joined}")
