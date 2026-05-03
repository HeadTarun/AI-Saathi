from __future__ import annotations

from langchain_core.tools import tool

import study_core


@tool
async def retrieve_aptitude_reasoning_knowledge(
    topic_name: str,
    subject: str | None = None,
    live: bool = True,
) -> dict:
    """Retrieve aptitude/reasoning knowledge from IndiaBix/GeeksforGeeks with an offline fallback."""
    return study_core.external_knowledge_for_topic(topic_name=topic_name, subject=subject, live=live)

