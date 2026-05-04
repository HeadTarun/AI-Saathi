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


def fake_events():
    yield {
        "event": "graph_started",
        "data": {"message": "Study agent started."},
    }
    yield {
        "event": "intent_detected",
        "data": {"agent": "teacher", "task": "teach_day", "message": "Opening lesson."},
    }
    yield {
        "event": "tool_started",
        "data": {"agent": "teacher", "tool_name": "study_teach_plan_day"},
    }
    yield {
        "event": "tool_finished",
        "data": {"agent": "teacher", "tool_name": "study_teach_plan_day", "ok": True},
    }
    yield {
        "event": "node_finished",
        "data": {"node": "teacher", "message": "teacher finished."},
    }
    yield {
        "event": "final_response",
        "data": {
            "agent": "teacher",
            "task": "teach_day",
            "message": "Opening lesson.",
            "data": {"topic_name": "Percentage", "status": "taught"},
            "events": [],
        },
    }


class StudyAgentStreamTests(unittest.TestCase):
    def setUp(self) -> None:
        from service.service import app

        self.client = TestClient(app)

    def test_sse_format_helper(self) -> None:
        from api.study_routes import _sse

        self.assertEqual(
            _sse("graph_started", {"message": "Ready"}),
            'event: graph_started\ndata: {"message": "Ready"}\n\n',
        )

    def test_agent_stream_formats_graph_events(self) -> None:
        with patch("api.study_routes.stream_study_graph_events", return_value=fake_events()):
            response = self.client.post(
                "/study/agent/stream",
                json={"user_id": "learner-1", "message": "Teach day", "context": {}},
            )

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn("event: graph_started\n", body)
        self.assertIn("event: intent_detected\n", body)
        self.assertIn("event: tool_started\n", body)
        self.assertIn("event: tool_finished\n", body)
        self.assertIn("event: node_finished\n", body)
        self.assertIn("event: final_response\n", body)
        self.assertNotIn("chain_of_thought", body)

    def test_teach_stream_emits_compat_complete_event(self) -> None:
        with patch("api.study_routes.stream_study_graph_events", return_value=fake_events()):
            response = self.client.get("/study/teach/day-1/stream?user_id=learner-1")

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: final_response\n", response.text)
        self.assertIn("event: complete\n", response.text)
        self.assertIn('"topic_name": "Percentage"', response.text)


if __name__ == "__main__":
    unittest.main()
