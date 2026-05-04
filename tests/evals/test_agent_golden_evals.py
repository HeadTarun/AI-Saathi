from __future__ import annotations

import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


HIDDEN_MARKERS = (
    "chain_of_thought",
    "hidden reasoning",
    "system prompt",
    "developer prompt",
    "scratchpad",
    "internal reasoning",
)


@dataclass(frozen=True)
class GoldenCase:
    name: str
    user_message: str
    decision: dict[str, Any]
    tool_response: dict[str, Any] | None
    expected_agent: str
    expected_task: str
    expected_tool: str | None
    expected_data_keys: tuple[str, ...]


class MockSupervisor:
    def __init__(self, decision: dict[str, Any]) -> None:
        self.decision = decision

    def with_structured_output(self, schema: Any) -> "MockSupervisor":
        self.schema = schema
        return self

    def invoke(self, input: Any, config: Any | None = None) -> dict[str, Any]:
        return self.decision


class RecordingTool:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def invoke(self, input: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(input)
        return self.response


GOLDEN_CASES = [
    GoldenCase(
        name="onboarding_build_plan",
        user_message="Create a 5 day SSC CGL plan for me.",
        decision={
            "agent": "planner",
            "task": "build_plan",
            "message": "Creating your study plan.",
            "tool_name": "study_build_plan",
            "tool_input": {"exam_id_or_name": "SSC CGL", "duration_days": 5, "level": "beginner"},
        },
        tool_response={"ok": True, "data": {"plan": {"plan_id": "plan-1", "duration_days": 5}}},
        expected_agent="planner",
        expected_task="build_plan",
        expected_tool="study_build_plan",
        expected_data_keys=("plan",),
    ),
    GoldenCase(
        name="teaching_plan_day",
        user_message="Teach my current plan day.",
        decision={
            "agent": "teacher",
            "task": "teach_day",
            "message": "Opening your lesson.",
            "tool_name": "study_teach_plan_day",
            "tool_input": {"plan_day_id": "day-1"},
        },
        tool_response={
            "ok": True,
            "data": {"log_id": "log-1", "topic_name": "Percentage", "status": "taught"},
        },
        expected_agent="teacher",
        expected_task="teach_day",
        expected_tool="study_teach_plan_day",
        expected_data_keys=("log_id", "topic_name", "status"),
    ),
    GoldenCase(
        name="generate_quiz",
        user_message="Generate a quiz on percentages.",
        decision={
            "agent": "quiz",
            "task": "generate_quiz",
            "message": "Generating your quiz.",
            "tool_name": "study_generate_quiz",
            "tool_input": {"topic_id": "topic-percentage", "num_questions": 5, "difficulty": 3},
        },
        tool_response={"ok": True, "data": {"attempt_id": "attempt-1", "total": 5, "questions": []}},
        expected_agent="quiz",
        expected_task="generate_quiz",
        expected_tool="study_generate_quiz",
        expected_data_keys=("attempt_id", "total", "questions"),
    ),
    GoldenCase(
        name="submit_quiz_results",
        user_message="Submit my quiz answers.",
        decision={
            "agent": "quiz",
            "task": "submit_quiz",
            "message": "Scoring your quiz.",
            "tool_name": "study_submit_quiz",
            "tool_input": {"attempt_id": "attempt-1", "user_answers": [0, 1, 2], "time_taken_secs": 120},
        },
        tool_response={
            "ok": True,
            "data": {"score": 2, "total": 3, "passed": False, "replan_triggered": True},
        },
        expected_agent="quiz",
        expected_task="submit_quiz",
        expected_tool="study_submit_quiz",
        expected_data_keys=("score", "total", "passed", "replan_triggered"),
    ),
    GoldenCase(
        name="replan_after_failure",
        user_message="I failed the quiz. Replan my remaining days.",
        decision={
            "agent": "replan",
            "task": "replan",
            "message": "Updating your remaining study days.",
            "tool_name": "study_replan_user",
            "tool_input": {},
        },
        tool_response={"ok": True, "data": {"updated_plan_id": "plan-1", "message": "Plan updated"}},
        expected_agent="replan",
        expected_task="replan",
        expected_tool="study_replan_user",
        expected_data_keys=("updated_plan_id", "message"),
    ),
    GoldenCase(
        name="progress_summary",
        user_message="Show my progress summary.",
        decision={
            "agent": "progress",
            "task": "progress_summary",
            "message": "Fetching your progress.",
            "tool_name": "study_get_progress",
            "tool_input": {},
        },
        tool_response={"ok": True, "data": {"topic_stats": [], "top_weaknesses": [], "activity": {}}},
        expected_agent="progress",
        expected_task="progress_summary",
        expected_tool="study_get_progress",
        expected_data_keys=("topic_stats", "top_weaknesses", "activity"),
    ),
    GoldenCase(
        name="ambiguous_user_message",
        user_message="Can you help me with my studies?",
        decision={
            "agent": "general_help",
            "task": "clarify_study_request",
            "message": "What would you like to work on: plan, lesson, quiz, progress, or replan?",
            "tool_name": None,
            "tool_input": {},
        },
        tool_response=None,
        expected_agent="general_help",
        expected_task="clarify_study_request",
        expected_tool=None,
        expected_data_keys=("answer", "request"),
    ),
]


class StudyAgentGoldenEvals(unittest.TestCase):
    def test_golden_agent_cases(self) -> None:
        for index, case in enumerate(GOLDEN_CASES, start=1):
            with self.subTest(case=case.name):
                final, tool = self._run_case(case, index)
                self._assert_shape(final)
                self._assert_no_hidden_reasoning(final)
                self.assertEqual(final["agent"], case.expected_agent)
                self.assertEqual(final["task"], case.expected_task)
                for key in case.expected_data_keys:
                    self.assertIn(key, final["data"])
                self._assert_tool_alignment(final, case.expected_tool)
                if case.expected_tool:
                    self.assertIsNotNone(tool)
                    self.assertEqual(len(tool.calls), 1)
                    self.assertEqual(tool.calls[0]["user_id"], f"eval-user-{index}")

    def _run_case(self, case: GoldenCase, index: int) -> tuple[dict[str, Any], RecordingTool | None]:
        from agents.langgraph_workflow import run_study_graph
        from agents.memory import LocalWorkflowMemory

        tool = RecordingTool(case.tool_response) if case.tool_response else None
        tools = {case.expected_tool: tool} if case.expected_tool and tool else {}
        final = run_study_graph(
            {
                "user_id": f"eval-user-{index}",
                "message": case.user_message,
                "thread_id": case.name,
                "request_id": f"eval-req-{index}",
            },
            llm=MockSupervisor(case.decision),
            tools=tools,
            memory=LocalWorkflowMemory(),
        )
        return final, tool

    def _assert_shape(self, final: dict[str, Any]) -> None:
        self.assertEqual(set(final), {"agent", "task", "message", "data", "events"})
        self.assertIsInstance(final["agent"], str)
        self.assertIsInstance(final["task"], str)
        self.assertIsInstance(final["message"], str)
        self.assertIsInstance(final["data"], dict)
        self.assertIsInstance(final["events"], list)

    def _assert_no_hidden_reasoning(self, final: dict[str, Any]) -> None:
        serialized = json.dumps(final, default=str).lower()
        for marker in HIDDEN_MARKERS:
            self.assertNotIn(marker, serialized)

    def _assert_tool_alignment(self, final: dict[str, Any], expected_tool: str | None) -> None:
        from agents.langgraph_workflow import TOOL_AGENT_BY_NAME

        tool_events = [
            event
            for event in final["events"]
            if isinstance(event, dict) and event.get("tool_name") not in (None, "none")
        ]
        if expected_tool is None:
            self.assertEqual(tool_events, [])
            return
        self.assertTrue(tool_events)
        selected_tool = tool_events[-1]["tool_name"]
        self.assertEqual(selected_tool, expected_tool)
        self.assertEqual(TOOL_AGENT_BY_NAME[selected_tool], final["agent"])


if __name__ == "__main__":
    unittest.main()
