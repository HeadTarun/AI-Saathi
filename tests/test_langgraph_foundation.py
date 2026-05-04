from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class LangGraphFoundationTests(unittest.TestCase):
    def test_langgraph_state_imports(self) -> None:
        from agents.langgraph_state import StudyAgentInput, StudyAgentOutput, StudyAgentState

        self.assertEqual(StudyAgentInput.__required_keys__, frozenset({"user_id", "message"}))
        self.assertIn("messages", StudyAgentState.__annotations__)
        self.assertIn("answer", StudyAgentOutput.__annotations__)

    def test_llm_fails_clearly_without_supported_key(self) -> None:
        from agents import llm

        env = dict(os.environ)
        env["GROQ_API_KEY"] = ""
        llm.get_llm.cache_clear()

        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(llm.LLMConfigurationError, "Set GROQ_API_KEY"):
                llm.get_llm()

    def test_llm_defaults_to_configured_model(self) -> None:
        from agents import llm

        with patch.dict(os.environ, {"DEFAULT_MODEL": "study-model"}, clear=False):
            self.assertEqual(llm.default_model_name(), "study-model")


if __name__ == "__main__":
    unittest.main()
