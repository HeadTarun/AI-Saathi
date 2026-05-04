from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class MemoryAwareSupervisor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def with_structured_output(self, schema: Any) -> "MemoryAwareSupervisor":
        return self

    def invoke(self, input: Any, config: Any | None = None) -> dict[str, Any]:
        content = input[-1].content
        self.calls.append(content)
        if "plan-1" in content:
            return {
                "agent": "teacher",
                "task": "teach_day",
                "message": "Continuing from your active plan.",
                "tool_name": "study_teach_plan_day",
                "tool_input": {"plan_day_id": "day-1"},
            }
        return {
            "agent": "planner",
            "task": "build_plan",
            "message": "Creating your study plan.",
            "tool_name": "study_build_plan",
            "tool_input": {"exam_id_or_name": "SSC CGL", "duration_days": 5},
        }


class MockTool:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def invoke(self, input: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(input)
        return self.response


class LangGraphMemoryTests(unittest.TestCase):
    def test_second_call_reuses_previous_checkpoint_memory(self) -> None:
        from agents.langgraph_workflow import run_study_graph
        from agents.memory import LocalWorkflowMemory

        memory = LocalWorkflowMemory()
        supervisor = MemoryAwareSupervisor()
        plan_tool = MockTool({"ok": True, "data": {"plan": {"plan_id": "plan-1"}}})
        teach_tool = MockTool({"ok": True, "data": {"topic_name": "Percentage", "status": "taught"}})
        tools = {
            "study_build_plan": plan_tool,
            "study_teach_plan_day": teach_tool,
        }

        first = run_study_graph(
            {"user_id": "learner-1", "message": "Build my plan", "thread_id": "session-1"},
            llm=supervisor,
            tools=tools,
            memory=memory,
        )
        second = run_study_graph(
            {"user_id": "learner-1", "message": "Teach the active day", "thread_id": "session-1"},
            llm=supervisor,
            tools=tools,
            memory=memory,
        )

        thread_key = memory.thread_key("learner-1", "session-1")
        loaded = memory.load(thread_key)
        self.assertEqual(first["agent"], "planner")
        self.assertEqual(second["agent"], "teacher")
        self.assertEqual(loaded["active_plan_id"], "plan-1")
        self.assertEqual(loaded["active_plan_day_id"], "day-1")
        self.assertEqual(loaded["latest_intent"], "teach")
        self.assertIn("plan-1", supervisor.calls[1])
        self.assertNotIn("GROQ_API_KEY", str(loaded))


if __name__ == "__main__":
    unittest.main()
