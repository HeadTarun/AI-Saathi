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


class ExistingStudyRoutesCompatTests(unittest.TestCase):
    def setUp(self) -> None:
        from service.service import app

        self.client = TestClient(app)

    def test_existing_exams_route_still_delegates_to_local_task(self) -> None:
        with patch("api.study_routes.run_study_task", return_value={"exams": {"SSC CGL": "ssc-cgl"}}):
            response = self.client.get("/study/exams")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"exams": {"SSC CGL": "ssc-cgl"}})

    def test_existing_teach_route_still_returns_teach_response(self) -> None:
        with patch(
            "api.study_routes.run_study_task",
            return_value={
                "log_id": "log-1",
                "lesson_content": "Lesson",
                "lesson_steps": [],
                "revision": None,
                "teacher_status": "complete",
                "topic_name": "Percentage",
                "status": "taught",
                "personalization": {},
            },
        ):
            response = self.client.post("/study/teach/day-1?user_id=learner-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["topic_name"], "Percentage")

    def test_existing_quiz_generate_route_still_returns_quiz_response(self) -> None:
        with patch(
            "api.study_routes.run_study_task",
            return_value={
                "attempt_id": "attempt-1",
                "questions": [{"question_text": "Q?", "options": ["A", "B"]}],
                "total": 1,
                "adaptive_context": {},
            },
        ):
            response = self.client.post(
                "/study/quiz/generate",
                json={"user_id": "learner-1", "topic_id": "topic-1"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["attempt_id"], "attempt-1")


if __name__ == "__main__":
    unittest.main()
