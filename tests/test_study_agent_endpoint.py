from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class StudyAgentEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        from service.service import app

        self.client = TestClient(app)

    def test_study_agent_success(self) -> None:
        expected = {
            "agent": "planner",
            "task": "build_plan",
            "message": "Creating your study plan.",
            "data": {"plan": {"plan_id": "plan-1"}},
            "events": [{"node": "supervisor"}],
        }
        with patch("api.study_routes.run_study_graph", return_value=expected) as mock_run:
            response = self.client.post(
                "/study/agent",
                json={
                    "user_id": "learner-1",
                    "message": "Build a plan",
                    "context": {"duration_days": 5},
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        mock_run.assert_called_once_with(
            {
                "user_id": "learner-1",
                "message": "Build a plan",
                "context": {"duration_days": 5},
            }
        )

    def test_study_agent_validation_error(self) -> None:
        response = self.client.post("/study/agent", json={"user_id": "", "message": ""})

        self.assertEqual(response.status_code, 422)

    def test_study_agent_missing_llm_config(self) -> None:
        from agents.llm import LLMConfigurationError

        with patch(
            "api.study_routes.run_study_graph",
            side_effect=LLMConfigurationError("Set GROQ_API_KEY"),
        ):
            response = self.client.post(
                "/study/agent",
                json={"user_id": "learner-1", "message": "Build a plan"},
            )

        self.assertEqual(response.status_code, 503)
        self.assertIn("Set GROQ_API_KEY", response.json()["detail"])

    def test_study_agent_tool_error_response(self) -> None:
        with patch(
            "api.study_routes.run_study_graph",
            return_value={
                "agent": "planner",
                "task": "build_plan",
                "message": "Tool failed",
                "data": {"error": {"type": "ToolError", "message": "missing topic"}},
                "events": [],
            },
        ):
            response = self.client.post(
                "/study/agent",
                json={"user_id": "learner-1", "message": "Build a plan"},
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"]["message"], "missing topic")


if __name__ == "__main__":
    unittest.main()
