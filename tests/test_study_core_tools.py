from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class StudyCoreToolTests(unittest.TestCase):
    def test_build_plan_schema_validation(self) -> None:
        from agents.tools import BuildPlanInput

        with self.assertRaises(ValidationError):
            BuildPlanInput(
                user_id="learner-1",
                exam_id_or_name="SSC CGL",
                duration_days=1,
            )

    def test_quiz_schema_defaults(self) -> None:
        from agents.tools import GenerateQuizInput

        parsed = GenerateQuizInput(user_id="learner-1", topic_id="topic-1")
        self.assertEqual(parsed.num_questions, 5)
        self.assertEqual(parsed.difficulty, 3)

    def test_get_active_plan_tool_mocked_call(self) -> None:
        from agents.tools import study_get_active_plan

        plan = {"id": "plan-1", "user_id": "learner-1", "days": []}
        with patch("agents.tools.study_core.get_active_plan", return_value=plan) as mock_get:
            result = study_get_active_plan.invoke({"user_id": "learner-1"})

        mock_get.assert_called_once_with("learner-1")
        self.assertEqual(result, {"ok": True, "data": {"plan": plan}})

    def test_tool_errors_are_structured(self) -> None:
        from agents.tools import study_get_active_plan

        with patch("agents.tools.study_core.get_active_plan", side_effect=ValueError("missing")):
            result = study_get_active_plan.invoke({"user_id": "learner-1"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "ValueError")
        self.assertEqual(result["error"]["message"], "missing")


if __name__ == "__main__":
    unittest.main()
