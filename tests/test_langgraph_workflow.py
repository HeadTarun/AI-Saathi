from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class MockSupervisor:
    def __init__(self, decision: dict[str, Any]) -> None:
        self.decision = decision

    def with_structured_output(self, schema: Any) -> "MockSupervisor":
        self.schema = schema
        return self

    def invoke(self, input: Any, config: Any | None = None) -> dict[str, Any]:
        return self.decision


class MockTool:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def invoke(self, input: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(input)
        return self.response


class LangGraphWorkflowTests(unittest.TestCase):
    def test_build_plan_intent_routes_to_planner_tool(self) -> None:
        from agents.langgraph_workflow import run_study_graph

        tool = MockTool({"ok": True, "data": {"plan": {"plan_id": "plan-1"}}})
        final = run_study_graph(
            {"user_id": "learner-1", "message": "Build a 5 day SSC plan"},
            llm=MockSupervisor(
                {
                    "agent": "planner",
                    "task": "build_plan",
                    "message": "Creating your study plan.",
                    "tool_name": "study_build_plan",
                    "tool_input": {
                        "exam_id_or_name": "SSC CGL",
                        "duration_days": 5,
                        "name": "Learner",
                        "level": "beginner",
                    },
                }
            ),
            tools={"study_build_plan": tool},
        )

        self.assertEqual(final["agent"], "planner")
        self.assertEqual(final["task"], "build_plan")
        self.assertEqual(final["data"]["plan"]["plan_id"], "plan-1")
        self.assertEqual(tool.calls[0]["user_id"], "learner-1")

    def test_teach_day_intent_routes_to_teacher_tool(self) -> None:
        from agents.langgraph_workflow import run_study_graph

        tool = MockTool({"ok": True, "data": {"topic_name": "Percentage", "status": "taught"}})
        final = run_study_graph(
            {"user_id": "learner-1", "message": "Teach today's lesson"},
            llm=MockSupervisor(
                {
                    "agent": "teacher",
                    "task": "teach_day",
                    "message": "Opening your lesson.",
                    "tool_name": "study_teach_plan_day",
                    "tool_input": {"plan_day_id": "day-1"},
                }
            ),
            tools={"study_teach_plan_day": tool},
        )

        self.assertEqual(final["agent"], "teacher")
        self.assertEqual(final["task"], "teach_day")
        self.assertEqual(final["data"]["topic_name"], "Percentage")
        self.assertEqual(tool.calls[0], {"plan_day_id": "day-1", "user_id": "learner-1"})

    def test_quiz_intent_routes_to_quiz_tool(self) -> None:
        from agents.langgraph_workflow import run_study_graph

        tool = MockTool({"ok": True, "data": {"attempt_id": "attempt-1", "total": 5}})
        final = run_study_graph(
            {"user_id": "learner-1", "message": "Generate a quiz"},
            llm=MockSupervisor(
                {
                    "agent": "quiz",
                    "task": "generate_quiz",
                    "message": "Generating your quiz.",
                    "tool_name": "study_generate_quiz",
                    "tool_input": {"topic_id": "topic-1", "num_questions": 5, "difficulty": 3},
                }
            ),
            tools={"study_generate_quiz": tool},
        )

        self.assertEqual(final["agent"], "quiz")
        self.assertEqual(final["task"], "generate_quiz")
        self.assertEqual(final["data"]["attempt_id"], "attempt-1")
        self.assertGreaterEqual(len(final["events"]), 3)


if __name__ == "__main__":
    unittest.main()
