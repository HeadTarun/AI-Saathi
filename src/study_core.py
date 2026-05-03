from __future__ import annotations

import random
import re
import urllib.error
import urllib.request
import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from typing import Any

from db import get_supabase


PASS_MARK = 65
PLANNER_VERSION = 3
EXTERNAL_FOUNDATION_EXAM_ID = "aptitude-reasoning-foundation"

EXTERNAL_FOUNDATION_TOPICS = [
    {
        "name": "Percentage",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 2,
        "hours": 2.5,
        "keywords": ["percent change", "fraction conversion", "base value"],
        "source_slug": "percentage",
    },
    {
        "name": "Profit & Loss",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 3,
        "hours": 3.0,
        "keywords": ["cost price", "selling price", "discount", "marked price"],
        "source_slug": "profit-and-loss",
    },
    {
        "name": "Ratio & Proportion",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 2,
        "hours": 2.5,
        "keywords": ["ratio", "proportion", "variation", "mixture"],
        "source_slug": "ratio-and-proportion",
    },
    {
        "name": "Time & Work",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 3,
        "hours": 3.0,
        "keywords": ["work rate", "efficiency", "pipes", "combined work"],
        "source_slug": "time-and-work",
    },
    {
        "name": "Time, Speed & Distance",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 3,
        "hours": 3.0,
        "keywords": ["speed", "distance", "relative speed", "trains"],
        "source_slug": "time-speed-and-distance",
    },
    {
        "name": "Number Series",
        "subject": "Reasoning Ability",
        "priority": "HIGH",
        "difficulty": 2,
        "hours": 2.0,
        "keywords": ["number pattern", "difference series", "multiplication pattern"],
        "source_slug": "number-series",
    },
    {
        "name": "Coding-Decoding",
        "subject": "Reasoning Ability",
        "priority": "HIGH",
        "difficulty": 2,
        "hours": 2.0,
        "keywords": ["letter positions", "substitution", "reverse alphabet"],
        "source_slug": "coding-decoding",
    },
    {
        "name": "Blood Relations",
        "subject": "Reasoning Ability",
        "priority": "MED",
        "difficulty": 2,
        "hours": 2.0,
        "keywords": ["family tree", "relations", "gender clues"],
        "source_slug": "blood-relations",
    },
    {
        "name": "Direction Sense",
        "subject": "Reasoning Ability",
        "priority": "MED",
        "difficulty": 2,
        "hours": 1.5,
        "keywords": ["directions", "turns", "distance from origin"],
        "source_slug": "direction-sense-test",
    },
    {
        "name": "Syllogism",
        "subject": "Reasoning Ability",
        "priority": "MED",
        "difficulty": 3,
        "hours": 2.5,
        "keywords": ["statements", "conclusions", "venn diagram"],
        "source_slug": "syllogism",
    },
]

RAG_APTITUDE_TOPICS = [
    {
        "name": "Percentage",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 2,
        "hours": 3.0,
        "query": "percentage percent increase decrease",
    },
    {
        "name": "Profit & Loss",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 3,
        "hours": 3.5,
        "query": "profit loss cost price selling price",
    },
    {
        "name": "Ratio & Proportion",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 2,
        "hours": 2.5,
        "query": "ratio proportion variation",
    },
    {
        "name": "Time & Work",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 3,
        "hours": 3.0,
        "query": "time work pipes cisterns efficiency",
    },
    {
        "name": "Time, Speed & Distance",
        "subject": "Quantitative Aptitude",
        "priority": "HIGH",
        "difficulty": 3,
        "hours": 3.0,
        "query": "time speed distance trains boats streams",
    },
    {
        "name": "Simple & Compound Interest",
        "subject": "Quantitative Aptitude",
        "priority": "MED",
        "difficulty": 3,
        "hours": 3.0,
        "query": "simple interest compound interest principal rate",
    },
    {
        "name": "Average",
        "subject": "Quantitative Aptitude",
        "priority": "MED",
        "difficulty": 2,
        "hours": 2.0,
        "query": "average mean numbers",
    },
]


def _table(name: str):
    return get_supabase().table(name)


def _data(response: Any) -> Any:
    return getattr(response, "data", None) or []


def _one(response: Any) -> dict[str, Any] | None:
    rows = _data(response)
    return rows[0] if rows else None


def _safe_upsert(table_name: str, row: dict[str, Any], *, on_conflict: str) -> None:
    optional_columns = {"source_type", "source_document_id", "source_query"}
    current = dict(row)
    while True:
        try:
            _table(table_name).upsert(current, on_conflict=on_conflict).execute()
            return
        except Exception as exc:
            message = str(exc)
            if "Could not find the table" in message and table_name in {"topic_lesson_material"}:
                return
            removed = False
            for column in list(optional_columns):
                if column in current and column in message:
                    current.pop(column, None)
                    removed = True
            if not removed:
                raise


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or uuid.uuid4().hex[:8]


def _summarize_chunk(content: str, max_len: int = 520) -> str:
    text = " ".join(str(content or "").split())
    return text[:max_len].rsplit(" ", 1)[0] if len(text) > max_len else text


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._skip = tag in {"script", "style", "noscript", "svg"}

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text and not self._skip:
            self.parts.append(text)


def _read_public_page(url: str, timeout: float = 2.5) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 AI-SAATHI study planner (+local learning helper)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(180_000).decode("utf-8", errors="ignore")
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        return ""
    parser = _TextExtractor()
    parser.feed(body)
    return _summarize_chunk(" ".join(parser.parts), max_len=900)


def external_knowledge_for_topic(topic_name: str, subject: str | None = None, live: bool = True) -> dict[str, Any]:
    """Fetch lightweight public study context, with an offline fallback for aptitude/reasoning."""
    match = next(
        (item for item in EXTERNAL_FOUNDATION_TOPICS if item["name"].lower() == topic_name.lower()),
        None,
    )
    slug = (match or {}).get("source_slug") or _slug(topic_name)
    sources = [
        {
            "name": "IndiaBix",
            "url": f"https://www.indiabix.com/aptitude/{slug}/",
        },
        {
            "name": "GeeksforGeeks",
            "url": f"https://www.geeksforgeeks.org/{slug}/",
        },
    ]
    excerpts = []
    if live:
        for source in sources:
            excerpt = _read_public_page(source["url"])
            if excerpt:
                excerpts.append({**source, "excerpt": excerpt})

    keywords = (match or {}).get("keywords") or [topic_name.lower(), "practice", "concept"]
    if not excerpts:
        excerpts = [
            {
                "name": "Built-in aptitude/reasoning fallback",
                "url": "",
                "excerpt": (
                    f"{topic_name} practice should start by identifying the question type, "
                    f"writing the given values or clues, applying the core rule, and checking "
                    f"the answer against all options. Focus keywords: {', '.join(keywords)}."
                ),
            }
        ]

    return {
        "topic_name": topic_name,
        "subject": subject or (match or {}).get("subject") or "Aptitude and Reasoning",
        "sources": excerpts,
        "keywords": keywords,
        "source_policy": "Use short public-page excerpts as grounding; do not copy full articles.",
    }


def _knowledge_material(topic: dict[str, Any], knowledge: dict[str, Any]) -> dict[str, Any]:
    topic_name = topic["topic_name"]
    sources = knowledge.get("sources") or []
    primary = sources[0] if sources else {}
    source_name = primary.get("name") or "fallback study source"
    excerpt = primary.get("excerpt") or ""
    keywords = knowledge.get("keywords") or []
    focus = ", ".join(keywords[:4]) or topic_name.lower()
    simple = (
        f"{topic_name} is a core {topic.get('subject', 'aptitude')} topic. "
        f"Use the {source_name} grounding to revise {focus}. "
        f"{excerpt}"
    )
    return {
        "id": f"lesson-{topic['id']}",
        "topic_id": topic["id"],
        "simple_explanation": _summarize_chunk(simple, max_len=900),
        "concept_points": [
            f"Identify whether the question is asking about {keyword}."
            for keyword in keywords[:3]
        ]
        or [f"Identify the exact {topic_name} pattern before calculating."],
        "worked_example": (
            f"Set up a small table for the given values or clues, apply the {topic_name} rule, "
            "then eliminate options that break the condition."
        ),
        "common_mistakes": [
            "Solving before writing the given data.",
            "Ignoring units, direction, or relation words.",
            "Choosing the first close option without checking all options.",
        ],
        "quick_trick": "Convert the wording into symbols, a table, or a sketch before selecting an option.",
        "practice_prompt": f"Practice 3 {topic_name} questions: one easy, one timed, and one with a trap option.",
        "recap": f"For {topic_name}, slow setup plus fast checking gives the best quiz accuracy.",
        "is_active": True,
    }


def _knowledge_quiz_templates(topic: dict[str, Any], knowledge: dict[str, Any]) -> list[dict[str, Any]]:
    topic_name = topic["topic_name"]
    difficulty = int(topic.get("difficulty") or 3)
    source = (knowledge.get("sources") or [{}])[0]
    source_name = source.get("name") or "study source"
    keyword = (knowledge.get("keywords") or [topic_name.lower()])[0]
    prompts = [
        (
            f"What is the best first move in a {topic_name} question?",
            ["Write the given data or clues", "Guess from options", "Ignore conditions", "Skip checking"],
            0,
            f"{source_name} style practice rewards careful setup before speed.",
        ),
        (
            f"Which focus area is most connected with {topic_name}?",
            [keyword.title(), "Unrelated vocabulary", "Long essay writing", "Random guessing"],
            0,
            f"{keyword} is part of the grounding collected for {topic_name}.",
        ),
        (
            f"Why should you verify every option in {topic_name}?",
            [
                "Trap options often satisfy only part of the condition",
                "All options are always correct",
                "Verification wastes marks",
                "The topic has no rules",
            ],
            0,
            "Checking options catches common aptitude and reasoning traps.",
        ),
        (
            f"When you fail a {topic_name} quiz, what should the next session do?",
            ["Revise the same weak pattern", "Move only to unrelated topics", "Stop practice", "Memorize option labels"],
            0,
            "The planner uses weak-topic history to repeat and strengthen the same pattern.",
        ),
    ]
    return [
        {
            "id": f"quiz-{topic['id']}-external-{index}",
            "topic_id": topic["id"],
            "template_type": "mcq",
            "difficulty": difficulty,
            "template_body": {"question_text": question, "options": options},
            "answer_key": {"correct_index": correct, "explanation": explanation},
            "is_active": True,
        }
        for index, (question, options, correct, explanation) in enumerate(prompts, start=1)
    ]


def ensure_external_foundation_source() -> dict[str, Any]:
    exam = {
        "id": EXTERNAL_FOUNDATION_EXAM_ID,
        "name": "Aptitude + Reasoning Foundation",
        "description": "Fallback syllabus grounded by IndiaBix and GeeksforGeeks-style aptitude/reasoning practice.",
        "syllabus_version": "external-foundation",
        "is_active": True,
        "source_type": "external_knowledge",
    }
    _safe_upsert("exams", exam, on_conflict="id")
    topics = []
    for index, item in enumerate(EXTERNAL_FOUNDATION_TOPICS, start=1):
        topics.append(
            {
                "id": f"{EXTERNAL_FOUNDATION_EXAM_ID}-topic-{_slug(item['name'])}",
                "exam_id": EXTERNAL_FOUNDATION_EXAM_ID,
                "subject": item["subject"],
                "topic_name": item["name"],
                "subtopics": item["keywords"],
                "difficulty": item["difficulty"],
                "priority": item["priority"],
                "estimated_hours": item["hours"],
                "prerequisite_ids": [],
                "template_ids": [],
                "source_query": item["source_slug"],
            }
        )
    for topic in topics:
        _safe_upsert("syllabus_topics", topic, on_conflict="id")
        knowledge = external_knowledge_for_topic(topic["topic_name"], topic["subject"], live=False)
        _safe_upsert("topic_lesson_material", _knowledge_material(topic, knowledge), on_conflict="id")
        for quiz in _knowledge_quiz_templates(topic, knowledge):
            _safe_upsert("quiz_templates", quiz, on_conflict="id")
    return exam


def _priority_rank(priority: str) -> int:
    return {"HIGH": 0, "MED": 1, "LOW": 2}.get(priority, 3)


def _rag_documents() -> list[dict[str, Any]]:
    return _data(_table("rag_documents").select("*").order("created_at", desc=True).execute())


def _document_chunks(document_id: str, query: str | None = None, limit: int = 3) -> list[dict[str, Any]]:
    request = (
        _table("rag_chunks")
        .select("id,content,metadata,chunk_index")
        .eq("document_id", document_id)
        .order("chunk_index")
    )
    if query:
        words = [word for word in re.split(r"\W+", query) if len(word) >= 4]
        if words:
            request = request.ilike("content", f"%{words[0]}%")
    rows = _data(request.limit(limit).execute())
    if rows or not query:
        return rows
    return _data(
        _table("rag_chunks")
        .select("id,content,metadata,chunk_index")
        .eq("document_id", document_id)
        .order("chunk_index")
        .limit(limit)
        .execute()
    )


def _all_resource_bundle(user_goal: str = "") -> dict[str, Any]:
    sync_rag_study_sources()
    ensure_external_foundation_source()
    exams = _data(_table("exams").select("*").eq("is_active", True).execute())
    topics = _data(_table("syllabus_topics").select("*").execute())
    docs = _rag_documents()
    chunks = []
    for doc in docs:
        for chunk in _document_chunks(doc["id"], user_goal, limit=8):
            chunks.append({**chunk, "document": doc})
    return {
        "exams": exams,
        "topics": topics,
        "documents": docs,
        "chunks": chunks,
    }


def _keywords(text: str) -> list[str]:
    stopwords = {
        "about",
        "after",
        "again",
        "also",
        "and",
        "are",
        "basic",
        "before",
        "build",
        "clear",
        "concept",
        "from",
        "goal",
        "have",
        "into",
        "learn",
        "plan",
        "practice",
        "prepare",
        "ready",
        "revise",
        "study",
        "that",
        "the",
        "this",
        "topic",
        "weak",
        "with",
    }
    words = [
        word.lower()
        for word in re.findall(r"[A-Za-z][A-Za-z0-9&+-]{2,}", text or "")
        if word.lower() not in stopwords
    ]
    return words


def _chunk_title(chunk: dict[str, Any], fallback: str) -> str:
    metadata = chunk.get("metadata") or {}
    for key in ("topic", "title", "heading", "section", "chapter"):
        value = metadata.get(key)
        if value:
            return str(value).strip()[:80]
    content = " ".join(str(chunk.get("content") or "").split())
    phrases = re.findall(r"\b[A-Z][A-Za-z0-9&+-]*(?:\s+[A-Z][A-Za-z0-9&+-]*){0,4}", content)
    return (phrases[0] if phrases else fallback).strip()[:80]


def _custom_topic_specs(resources: dict[str, Any], duration_days: int, user_goal: str) -> list[dict[str, Any]]:
    goal_words = set(_keywords(user_goal))
    chunk_groups: dict[str, dict[str, Any]] = {}
    for index, chunk in enumerate(resources["chunks"], start=1):
        title = _chunk_title(chunk, f"Resource Focus {index}")
        content = str(chunk.get("content") or "")
        words = _keywords(f"{title} {content}")
        overlap = len(goal_words.intersection(words)) if goal_words else 0
        score = overlap * 5 + min(8, len(words) // 40) + (3 if title != f"Resource Focus {index}" else 0)
        key = _slug(title)
        group = chunk_groups.setdefault(
            key,
            {
                "name": title,
                "subject": "Custom RAG Study",
                "priority": "HIGH" if overlap else "MED",
                "difficulty": 3,
                "hours": 2.5,
                "score": 0,
                "chunks": [],
                "keywords": Counter(),
                "source_document_ids": set(),
            },
        )
        group["score"] += score
        group["chunks"].append(chunk)
        group["keywords"].update(words[:40])
        if chunk.get("document_id"):
            group["source_document_ids"].add(chunk["document_id"])

    specs = sorted(chunk_groups.values(), key=lambda item: (-item["score"], item["name"]))
    if len(specs) < duration_days:
        for topic in resources["topics"]:
            text = " ".join(
                [
                    str(topic.get("topic_name") or ""),
                    str(topic.get("subject") or ""),
                    " ".join(topic.get("subtopics") or []),
                ]
            )
            words = _keywords(text)
            overlap = len(goal_words.intersection(words)) if goal_words else 0
            specs.append(
                {
                    "name": topic.get("topic_name") or topic["id"],
                    "subject": topic.get("subject") or "Supabase Syllabus",
                    "priority": topic.get("priority") or ("HIGH" if overlap else "MED"),
                    "difficulty": int(topic.get("difficulty") or 3),
                    "hours": float(topic.get("estimated_hours") or 2.0),
                    "score": overlap * 5 + _priority_rank(topic.get("priority") or "MED"),
                    "chunks": [],
                    "keywords": Counter(words),
                    "source_document_ids": set(),
                }
            )

    selected = specs[: max(duration_days, min(12, duration_days * 2))]
    if not selected:
        raise ValueError("No Supabase RAG resources or syllabus topics are ready for a custom plan.")
    return selected


def _custom_lesson_material(topic: dict[str, Any], spec: dict[str, Any], user_goal: str) -> dict[str, Any]:
    chunks = spec.get("chunks") or []
    excerpt = _summarize_chunk(" ".join(str(chunk.get("content") or "") for chunk in chunks), max_len=900)
    top_terms = [term for term, _count in (spec.get("keywords") or Counter()).most_common(5)]
    focus = ", ".join(top_terms[:4]) or topic["topic_name"].lower()
    explanation = (
        excerpt
        or f"This custom topic was selected from your Supabase syllabus resources for: {user_goal or topic['topic_name']}."
    )
    return {
        "id": f"lesson-{topic['id']}",
        "topic_id": topic["id"],
        "simple_explanation": explanation,
        "concept_points": [
            f"Connect this lesson to your goal: {user_goal or 'finish the current study run'}.",
            f"Focus keywords from Supabase resources: {focus}.",
            "Use the saved source material before moving to timed practice.",
        ],
        "worked_example": excerpt or f"Create a short worked example for {topic['topic_name']} from the matched source material.",
        "common_mistakes": [
            "Jumping to practice before reading the matched resource.",
            "Treating a repeated keyword as mastery without solving examples.",
            "Skipping revision from the previous custom-plan day.",
        ],
        "quick_trick": "Turn the source excerpt into a three-step note: rule, example, check.",
        "practice_prompt": f"Practice one easy and one timed question for {topic['topic_name']}.",
        "recap": f"{topic['topic_name']} was chosen because it matched your Supabase resources and current goal.",
        "is_active": True,
    }


def _custom_quiz_templates(topic: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, Any]]:
    top_term = next(iter((spec.get("keywords") or Counter()).keys()), topic["topic_name"].lower())
    return [
        {
            "id": f"quiz-{topic['id']}-source",
            "topic_id": topic["id"],
            "template_type": "mcq",
            "difficulty": int(topic.get("difficulty") or 3),
            "template_body": {
                "question_text": f"What should you do first while studying {topic['topic_name']}?",
                "options": [
                    "Read the matched Supabase source excerpt",
                    "Skip directly to random guessing",
                    "Ignore the topic goal",
                    "Mark the day complete",
                ],
            },
            "answer_key": {
                "correct_index": 0,
                "explanation": "The custom plan is grounded in the matched Supabase RAG resources.",
            },
            "is_active": True,
        },
        {
            "id": f"quiz-{topic['id']}-focus",
            "topic_id": topic["id"],
            "template_type": "mcq",
            "difficulty": int(topic.get("difficulty") or 3),
            "template_body": {
                "question_text": f"Which focus term is connected to {topic['topic_name']}?",
                "options": [str(top_term).title(), "Unrelated topic", "No revision", "Random answer"],
            },
            "answer_key": {
                "correct_index": 0,
                "explanation": "This term came from the Supabase resource text used to build the plan.",
            },
            "is_active": True,
        },
    ]


def run_custom_rag_plan_workflow(
    user_id: str,
    duration_days: int,
    start_date: str | None = None,
    name: str = "Learner",
    level: str = "beginner",
    email: str | None = None,
    user_goal: str | None = None,
) -> dict[str, Any]:
    duration_days = max(2, min(7, int(duration_days)))
    goal = (user_goal or "").strip()
    resources = _all_resource_bundle(goal)
    exam_id = f"custom-rag-{_slug(user_id)}"
    source_names = [str(doc.get("filename") or doc["id"]) for doc in resources["documents"]]
    exam = {
        "id": exam_id,
        "name": f"Custom RAG Plan - {name or 'Learner'} ({_slug(user_id)})",
        "description": "Personal plan built from all available Supabase syllabus and RAG resources.",
        "syllabus_version": "custom-rag",
        "is_active": True,
        "source_type": "custom_rag",
        "source_document_id": (resources["documents"][0]["id"] if resources["documents"] else None),
    }
    _safe_upsert("exams", exam, on_conflict="id")
    specs = _custom_topic_specs(resources, duration_days, goal)

    topics = []
    for index, spec in enumerate(specs, start=1):
        topic = {
            "id": f"{exam_id}-topic-{index:02d}-{_slug(spec['name'])}",
            "exam_id": exam_id,
            "subject": spec.get("subject") or "Custom RAG Study",
            "topic_name": spec["name"],
            "subtopics": [term for term, _count in (spec.get("keywords") or Counter()).most_common(6)],
            "difficulty": int(spec.get("difficulty") or 3),
            "priority": spec.get("priority") or "MED",
            "estimated_hours": float(spec.get("hours") or 2.0),
            "prerequisite_ids": [],
            "template_ids": [],
            "source_document_id": next(iter(spec.get("source_document_ids") or []), None),
            "source_query": goal or spec["name"],
        }
        _safe_upsert("syllabus_topics", topic, on_conflict="id")
        _safe_upsert("topic_lesson_material", _custom_lesson_material(topic, spec, goal), on_conflict="id")
        for quiz in _custom_quiz_templates(topic, spec):
            _safe_upsert("quiz_templates", quiz, on_conflict="id")
        topics.append(
            {
                "id": topic["id"],
                "name": topic["topic_name"],
                "priority": topic["priority"],
                "difficulty": topic["difficulty"],
            }
        )

    start = date.fromisoformat(start_date).isoformat() if start_date else date.today().isoformat()
    weak_scores = _weak_scores(user_id)
    ordered_days = compute_ordered_plan_days(topics, weak_scores, duration_days, start)
    plan_record = create_study_plan_record(
        user_id=user_id,
        exam_id_or_name=exam_id,
        duration_days=duration_days,
        start_date=start,
        name=name,
        level=level,
        email=email,
        meta={
            "workflow": "custom_rag_planner",
            "user_goal": goal,
            "resource_counts": {
                "exams": len(resources["exams"]),
                "syllabus_topics": len(resources["topics"]),
                "rag_documents": len(resources["documents"]),
                "rag_chunks_used": len(resources["chunks"]),
            },
            "rag_sources": source_names[:10],
            "topic_count": len(topics),
            "weak_topics_considered": len(weak_scores),
        },
    )
    created_days = create_study_plan_days(plan_record["id"], ordered_days)
    plan = _plan_payload(plan_record)
    workflow = [
        {"step": "fetch_supabase_resources", "status": "complete", "resources": plan_record["meta"]["resource_counts"]},
        {"step": "rank_rag_topics", "status": "complete", "topics": len(topics)},
        {"step": "create_custom_exam", "status": "complete", "exam_id": exam_id},
        {"step": "create_study_plan", "status": "complete", "plan_id": plan_record["id"]},
        {"step": "create_plan_days", "status": "complete", "days_created": len(created_days)},
    ]
    return {"plan": plan, "workflow": workflow, "ordered_days": ordered_days}


def sync_rag_study_sources() -> list[dict[str, Any]]:
    docs = _rag_documents()
    created = []
    for doc in docs:
        exam_id = f"exam-{doc['id']}"
        name = str(doc.get("filename") or "Uploaded Study Book").replace(".pdf", "").strip()
        row = {
            "id": exam_id,
            "name": name,
            "description": "Study plan from your uploaded book",
            "syllabus_version": "uploaded",
            "is_active": True,
            "source_type": "rag_document",
            "source_document_id": doc["id"],
        }
        _safe_upsert("exams", row, on_conflict="id")
        _ensure_rag_topics_for_exam(exam_id, doc["id"])
        created.append(row)
    return created


def _ensure_rag_topics_for_exam(exam_id: str, document_id: str) -> None:
    topics = []
    lessons = []
    quizzes = []
    for index, item in enumerate(RAG_APTITUDE_TOPICS, start=1):
        topic_id = f"{exam_id}-topic-{_slug(item['name'])}"
        chunks = _document_chunks(document_id, item["query"], limit=2)
        excerpt = _summarize_chunk(" ".join(chunk.get("content", "") for chunk in chunks))
        explanation = (
            excerpt
            or f"Study {item['name']} from the uploaded aptitude book, then practice one short question."
        )
        topics.append(
            {
                "id": topic_id,
                "exam_id": exam_id,
                "subject": item["subject"],
                "topic_name": item["name"],
                "subtopics": [item["query"]],
                "difficulty": item["difficulty"],
                "priority": item["priority"],
                "estimated_hours": item["hours"],
                "prerequisite_ids": [],
                "template_ids": [],
                "source_document_id": document_id,
                "source_query": item["query"],
            }
        )
        lessons.append(
            {
                "id": f"lesson-{topic_id}",
                "topic_id": topic_id,
                "simple_explanation": explanation,
                "concept_points": [
                    f"Read the {item['name']} section from the uploaded book slowly.",
                    "Write the given values before calculating.",
                    "Check the final answer with the options.",
                ],
                "worked_example": excerpt or f"Use one solved example from the uploaded book for {item['name']}.",
                "common_mistakes": [
                    "Starting calculation before organizing the data.",
                    "Using the wrong base value or unit.",
                    "Choosing an option without checking.",
                ],
                "quick_trick": "Convert the question into a small equation or table first.",
                "practice_prompt": f"Try one {item['name']} question from the uploaded book and explain each step.",
                "recap": f"{item['name']} improves when you set up the values first and verify the final option.",
                "is_active": True,
            }
        )
        quizzes.extend(
            [
                {
                    "id": f"quiz-{topic_id}-setup",
                    "topic_id": topic_id,
                    "template_type": "mcq",
                    "difficulty": item["difficulty"],
                    "template_body": {
                        "question_text": f"What is the best first step for {item['name']}?",
                        "options": [
                            "Guess quickly",
                            "Write the given values",
                            "Ignore units",
                            "Skip checking",
                        ],
                    },
                    "answer_key": {
                        "correct_index": 1,
                        "explanation": "Writing the given values makes the method clear.",
                    },
                    "is_active": True,
                },
                {
                    "id": f"quiz-{topic_id}-check",
                    "topic_id": topic_id,
                    "template_type": "mcq",
                    "difficulty": item["difficulty"],
                    "template_body": {
                        "question_text": f"Why should you check your answer in {item['name']}?",
                        "options": [
                            "To catch calculation and unit mistakes",
                            "To make the question unrelated",
                            "To avoid practice",
                            "To skip the concept",
                        ],
                    },
                    "answer_key": {
                        "correct_index": 0,
                        "explanation": "Checking catches common mistakes before you submit.",
                    },
                    "is_active": True,
                },
                {
                    "id": f"quiz-{topic_id}-revise",
                    "topic_id": topic_id,
                    "template_type": "mcq",
                    "difficulty": item["difficulty"],
                    "template_body": {
                        "question_text": f"What should you revise after a weak score in {item['name']}?",
                        "options": [
                            "Only unrelated topics",
                            "The same weak concept",
                            "Nothing",
                            "Only easy questions",
                        ],
                    },
                    "answer_key": {
                        "correct_index": 1,
                        "explanation": "Targeted revision improves the weak concept fastest.",
                    },
                    "is_active": True,
                },
            ]
        )
    for topic in topics:
        _safe_upsert("syllabus_topics", topic, on_conflict="id")
    for lesson in lessons:
        _safe_upsert("topic_lesson_material", lesson, on_conflict="id")
    for quiz in quizzes:
        _safe_upsert("quiz_templates", quiz, on_conflict="id")


def _exam_id(value: str) -> str:
    rows = _data(_table("exams").select("id,name").eq("is_active", True).execute())
    for row in rows:
        if value in (row.get("id"), row.get("name")):
            return row["id"]

    if value == EXTERNAL_FOUNDATION_EXAM_ID:
        ensure_external_foundation_source()
        return EXTERNAL_FOUNDATION_EXAM_ID

    raise ValueError("This exam is not ready yet.")


def _exam_name(exam_id: str) -> str:
    row = _one(_table("exams").select("name").eq("id", exam_id).limit(1).execute())
    return row["name"] if row else exam_id


def _ensure_user(
    user_id: str,
    name: str = "Learner",
    level: str = "beginner",
    exam_id: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    existing = _one(_table("users").select("*").eq("id", user_id).limit(1).execute()) or {}
    row = {
        "id": user_id,
        "name": name or existing.get("name") or "Learner",
        "email": email or existing.get("email") or f"{user_id}@local.study",
        "level": level or existing.get("level") or "beginner",
        "target_exam_id": exam_id or existing.get("target_exam_id"),
        "timezone": existing.get("timezone") or "Asia/Kolkata",
    }
    return _one(_table("users").upsert(row, on_conflict="id").execute()) or row


def _weak_scores(user_id: str) -> dict[str, float]:
    rows = _data(_table("user_performance").select("*").eq("user_id", user_id).execute())
    return {row["topic_id"]: float(row.get("weakness_score") or 0) for row in rows}


def _performance_row(user_id: str, topic_id: str) -> dict[str, Any] | None:
    return _one(
        _table("user_performance")
        .select("*")
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .limit(1)
        .execute()
    )


def _adaptive_context(user_id: str, topic_id: str, base_difficulty: int) -> dict[str, Any]:
    performance = _performance_row(user_id, topic_id) or {}
    attempts = int(performance.get("attempts") or 0)
    accuracy = float(performance.get("accuracy") or 0.0)
    weakness = float(performance.get("weakness_score") or 50.0)
    difficulty = max(1, min(5, int(base_difficulty or 3)))
    reason = "topic_default"

    if attempts >= 3 and accuracy >= 85:
        difficulty = min(5, difficulty + 1)
        reason = "strong_accuracy_raise_difficulty"
    elif attempts >= 3 and (accuracy < PASS_MARK or weakness >= 60):
        difficulty = max(1, difficulty - 1)
        reason = "weak_topic_lower_difficulty"

    return {
        "source": "supabase_user_performance",
        "attempts": attempts,
        "accuracy": round(accuracy, 2),
        "weakness_score": round(weakness, 2),
        "base_difficulty": max(1, min(5, int(base_difficulty or 3))),
        "adapted_difficulty": difficulty,
        "reason": reason,
        "recommended_extra_mins": 20 if weakness >= 60 else 0,
    }


def list_exams() -> dict[str, str]:
    rows = _data(_table("exams").select("id,name").eq("is_active", True).order("name").execute())
    if not rows:
        ensure_external_foundation_source()
        rows = _data(_table("exams").select("id,name").eq("is_active", True).order("name").execute())
    return {row["name"]: row["id"] for row in rows}


def list_topics(exam_id_or_name: str) -> list[dict[str, Any]]:
    exam_id = _exam_id(exam_id_or_name)
    exam = _one(_table("exams").select("*").eq("id", exam_id).limit(1).execute())
    document_id = (exam or {}).get("source_document_id")
    if not document_id and exam_id.startswith("exam-doc-"):
        document_id = exam_id.removeprefix("exam-")
    if document_id:
        _ensure_rag_topics_for_exam(exam_id, document_id)
    rows = _data(
        _table("syllabus_topics")
        .select("*")
        .eq("exam_id", exam_id)
        .order("priority")
        .order("difficulty")
        .execute()
    )
    if not rows and exam_id == EXTERNAL_FOUNDATION_EXAM_ID:
        ensure_external_foundation_source()
        rows = _data(
            _table("syllabus_topics")
            .select("*")
            .eq("exam_id", exam_id)
            .order("priority")
            .order("difficulty")
            .execute()
        )
    return [
        {
            "id": row["id"],
            "name": row["topic_name"],
            "topic_id": row["id"],
            "topic_name": row["topic_name"],
            "subject": row["subject"],
            "priority": row["priority"],
            "difficulty": row["difficulty"],
            "hours": float(row.get("estimated_hours") or 0),
            "estimated_hours": float(row.get("estimated_hours") or 0),
            "prerequisite_ids": row.get("prerequisite_ids") or [],
            "subtopics": row.get("subtopics") or [],
        }
        for row in rows
    ]


def compute_ordered_plan_days(
    topics: list[dict[str, Any]],
    weak_scores: dict[str, float],
    duration_days: int,
    start_date: str,
) -> list[dict[str, Any]]:
    if not topics:
        raise ValueError("Study content for this exam is not ready yet.")
    start = date.fromisoformat(start_date)
    ordered_topics = sorted(
        topics,
        key=lambda topic: (
            -weak_scores.get(topic["id"], 0),
            _priority_rank(topic["priority"]),
            topic["difficulty"],
            topic["name"],
        ),
    )
    days = []
    for index in range(duration_days):
        topic = ordered_topics[index % len(ordered_topics)]
        weak = weak_scores.get(topic["id"], 0) >= 60
        days.append(
            {
                "day_number": index + 1,
                "scheduled_date": (start + timedelta(days=index)).isoformat(),
                "topic_id": topic["id"],
                "topic_name": topic["name"],
                "revision_topic_ids": [days[index - 1]["topic_id"]] if index >= 1 else [],
                "allocated_minutes": 110 if weak else 90,
                "status": "pending",
                "reason": "weak_area" if weak else "priority_order",
            }
        )
    return days


def create_study_plan_record(
    user_id: str,
    exam_id_or_name: str,
    duration_days: int,
    start_date: str | None = None,
    name: str = "Learner",
    level: str = "beginner",
    email: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    duration_days = max(2, min(7, int(duration_days)))
    exam_id = _exam_id(exam_id_or_name)
    start = date.fromisoformat(start_date) if start_date else date.today()
    end = start + timedelta(days=duration_days - 1)
    _ensure_user(user_id, name=name, level=level, exam_id=exam_id, email=email)
    (
        _table("study_plans")
        .update({"status": "abandoned"})
        .eq("user_id", user_id)
        .eq("status", "active")
        .execute()
    )

    plan = {
        "id": _new_id("plan"),
        "user_id": user_id,
        "exam_id": exam_id,
        "level": level,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "duration_days": duration_days,
        "status": "active",
        "planner_version": PLANNER_VERSION,
        "meta": {"pass_mark": PASS_MARK, **(meta or {})},
    }
    _table("study_plans").insert(plan).execute()
    return plan


def create_study_plan_days(
    plan_id: str,
    ordered_days: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = [
        {
            "id": _new_id("day"),
            "plan_id": plan_id,
            "day_number": day["day_number"],
            "scheduled_date": day["scheduled_date"],
            "topic_id": day["topic_id"],
            "revision_topic_ids": day.get("revision_topic_ids") or [],
            "allocated_minutes": day.get("allocated_minutes", 90),
            "status": day.get("status") or "pending",
        }
        for day in ordered_days
        if day.get("topic_id")
    ]
    if rows:
        _table("study_plan_days").insert(rows).execute()
    return rows


def run_plan_workflow(
    user_id: str,
    exam_id_or_name: str,
    duration_days: int,
    start_date: str | None = None,
    name: str = "Learner",
    level: str = "beginner",
    email: str | None = None,
    user_goal: str | None = None,
) -> dict[str, Any]:
    duration_days = max(2, min(7, int(duration_days)))
    exam_id = _exam_id(exam_id_or_name)
    topics = list_topics(exam_id)
    if not topics:
        raise ValueError("Study content for this exam is not ready yet.")

    start = date.fromisoformat(start_date).isoformat() if start_date else date.today().isoformat()
    weak_scores = _weak_scores(user_id)
    ordered_days = compute_ordered_plan_days(topics, weak_scores, duration_days, start)
    plan_record = create_study_plan_record(
        user_id=user_id,
        exam_id_or_name=exam_id,
        duration_days=duration_days,
        start_date=start,
        name=name,
        level=level,
        email=email,
        meta={
            "workflow": "planner_create_loop",
            "weak_topics_considered": len(weak_scores),
            "topic_count": len(topics),
            "user_goal": user_goal or "",
        },
    )
    created_days = create_study_plan_days(plan_record["id"], ordered_days)
    plan = _plan_payload(plan_record)
    workflow = [
        {"step": "ensure_user", "status": "complete", "user_id": user_id},
        {"step": "fetch_syllabus", "status": "complete", "topics": len(topics)},
        {"step": "fetch_weak_areas", "status": "complete", "weak_topics": len(weak_scores)},
        {"step": "compute_topic_order", "status": "complete", "days": len(ordered_days)},
        {"step": "create_study_plan", "status": "complete", "plan_id": plan_record["id"]},
        {"step": "create_plan_days", "status": "complete", "days_created": len(created_days)},
    ]
    return {"plan": plan, "workflow": workflow, "ordered_days": ordered_days}


def _topic_map(topic_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not topic_ids:
        return {}
    rows = _data(_table("syllabus_topics").select("*").in_("id", topic_ids).execute())
    return {row["id"]: row for row in rows}


def _best_day_scores(user_id: str, plan_day_ids: list[str]) -> dict[str, float]:
    if not plan_day_ids:
        return {}
    rows = _data(
        _table("quiz_attempts")
        .select("plan_day_id,accuracy")
        .eq("user_id", user_id)
        .in_("plan_day_id", plan_day_ids)
        .execute()
    )
    scores: dict[str, float] = {}
    for row in rows:
        day_id = row.get("plan_day_id")
        accuracy = row.get("accuracy")
        if not day_id or accuracy is None:
            continue
        scores[day_id] = max(scores.get(day_id, 0.0), float(accuracy))
    return scores


def _plan_payload(plan: dict[str, Any]) -> dict[str, Any]:
    days = _data(
        _table("study_plan_days")
        .select("*")
        .eq("plan_id", plan["id"])
        .order("day_number")
        .execute()
    )
    topics = _topic_map([day["topic_id"] for day in days if day.get("topic_id")])
    best_scores = _best_day_scores(plan["user_id"], [day["id"] for day in days])
    payload_days = []
    for index, day in enumerate(days):
        topic = topics.get(day.get("topic_id"), {})
        previous_day = payload_days[index - 1] if index > 0 else None
        unlocked = index == 0 or float((previous_day or {}).get("best_score") or 0) >= PASS_MARK
        payload_days.append(
            {
                "id": day["id"],
                "plan_day_id": day["id"],
                "day_number": day["day_number"],
                "scheduled_date": day["scheduled_date"],
                "topic_id": day["topic_id"],
                "topic": topic.get("topic_name", "Content not ready"),
                "topic_name": topic.get("topic_name", "Content not ready"),
                "subject": topic.get("subject", ""),
                "priority": topic.get("priority", "MED"),
                "difficulty": topic.get("difficulty", 3),
                "allocated_minutes": day["allocated_minutes"],
                "revision_topic_ids": day.get("revision_topic_ids") or [],
                "status": day["status"],
                "taught_at": day.get("taught_at"),
                "best_score": round(best_scores.get(day["id"], 0.0), 2),
                "pass_mark": PASS_MARK,
                "unlocked": unlocked,
                "unlock_reason": "" if unlocked else f"Score {PASS_MARK}% on Day {index} quiz to unlock.",
            }
        )
    return {
        "plan_id": plan["id"],
        "id": plan["id"],
        "user_id": plan["user_id"],
        "exam_id": plan["exam_id"],
        "exam": _exam_name(plan["exam_id"]),
        "level": plan.get("level", "beginner"),
        "start_date": plan["start_date"],
        "end_date": plan["end_date"],
        "duration": plan["duration_days"],
        "duration_days": plan["duration_days"],
        "status": plan["status"],
        "created_at": plan.get("created_at"),
        "days": payload_days,
        "meta": plan.get("meta") or {},
    }


def build_study_plan(
    user_id: str,
    exam_id_or_name: str,
    duration_days: int,
    start_date: str | None = None,
    name: str = "Learner",
    level: str = "beginner",
) -> dict[str, Any]:
    return run_plan_workflow(
        user_id=user_id,
        exam_id_or_name=exam_id_or_name,
        duration_days=duration_days,
        start_date=start_date,
        name=name,
        level=level,
    )["plan"]


def get_active_plan(user_id: str) -> dict[str, Any] | None:
    plan = _one(
        _table("study_plans")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return _plan_payload(plan) if plan else None


def get_plan_by_day(plan_day_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    day = _one(_table("study_plan_days").select("*").eq("id", plan_day_id).limit(1).execute())
    if not day:
        return None
    plan = _one(_table("study_plans").select("*").eq("id", day["plan_id"]).limit(1).execute())
    if not plan:
        return None
    full_plan = _plan_payload(plan)
    full_day = next((item for item in full_plan["days"] if item["id"] == plan_day_id), None)
    return (full_plan, full_day) if full_day else None


def _lesson_material(topic_id: str) -> dict[str, Any] | None:
    return _one(
        _table("topic_lesson_material")
        .select("*")
        .eq("topic_id", topic_id)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )


def lesson_for_topic(topic_name: str, level: str = "beginner") -> str:
    sync_rag_study_sources()
    topic = _one(
        _table("syllabus_topics")
        .select("*")
        .ilike("topic_name", f"%{topic_name}%")
        .limit(1)
        .execute()
    )
    if not topic:
        raise ValueError("This lesson is not ready yet.")
    material = _lesson_material(topic["id"])
    if not material:
        material = _knowledge_material(
            topic,
            external_knowledge_for_topic(topic["topic_name"], topic.get("subject")),
        )
        _safe_upsert("topic_lesson_material", material, on_conflict="id")
    steps = _build_lesson_steps(
        topic,
        material,
        revision=None,
        personalization={
            "attempts": 0,
            "accuracy": 0,
            "weakness_score": 50,
            "level": level,
            "user_goal": "",
            "source": "supabase_topic_lesson_material",
        },
    )
    return _plain_lesson_content(steps)


def _revision_for_topic(topic_id: str | None) -> dict[str, Any] | None:
    if not topic_id:
        return None
    topic = _topic_map([topic_id]).get(topic_id)
    material = _lesson_material(topic_id)
    if not topic or not material:
        return None
    points = material.get("concept_points") or []
    return {
        "topic_id": topic_id,
        "topic_name": topic.get("topic_name", "Previous topic"),
        "summary": points[0] if points else material.get("simple_explanation", ""),
        "quick_check": material.get("practice_prompt") or material.get("quick_trick") or "",
    }


def _build_lesson_steps(
    topic: dict[str, Any],
    material: dict[str, Any],
    revision: dict[str, Any] | None,
    personalization: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    topic_name = topic["topic_name"]
    level = str((personalization or {}).get("level") or "beginner")
    attempts = int((personalization or {}).get("attempts") or 0)
    accuracy = round(float((personalization or {}).get("accuracy") or 0))
    weakness = round(float((personalization or {}).get("weakness_score") or 50))
    learner_goal = str((personalization or {}).get("user_goal") or "").strip()
    extra_focus = weakness >= 60 or (attempts > 0 and accuracy < PASS_MARK)
    concept_points = material.get("concept_points") or []
    mistakes = material.get("common_mistakes") or []
    trick = material.get("quick_trick") or "Write the givens first, then solve only the part the option asks for."
    example = material.get("worked_example") or f"Take one {topic_name} question and turn the words into a tiny table."
    goal_line = f"\nYour goal today: {learner_goal}" if learner_goal else ""
    tone_line = (
        "I will slow down at the setup step because your saved attempts show this topic needs reinforcement."
        if extra_focus
        else "I will keep the pace crisp and push you toward faster option checking."
    )
    real_world = _real_world_example(topic_name)
    first_question = _socratic_question(topic_name)
    steps: list[dict[str, Any]] = []
    steps.append(
        {
            "id": "socratic-hook",
            "title": "Think First",
            "kind": "socratic",
            "content": (
                f"Before I teach {topic_name}, answer this in your head: {first_question}\n\n"
                f"Level: {level}. Saved accuracy: {accuracy}% from {attempts} attempts. {tone_line}{goal_line}"
            ),
            "checkpoint": "Do not calculate yet. First name what is given, what is asked, and which clue matters most.",
        }
    )
    if revision:
        steps.append(
            {
                "id": "review",
                "title": f"Connect Yesterday",
                "kind": "review",
                "content": (
                    f"Yesterday's idea, {revision['topic_name']}, is useful here. "
                    f"Recall it in one sentence: {revision['summary']}"
                ),
                "checkpoint": f"Quick oral check: {revision['quick_check']}",
            }
        )
    steps.extend(
        [
            {
                "id": "concept",
                "title": "Build The Idea",
                "kind": "concept",
                "content": (
                    f"Here is the clean idea behind {topic_name}:\n"
                    f"{material.get('simple_explanation') or 'This lesson is being prepared.'}\n\n"
                    "Now pause: which single word or number in the question controls the method?"
                ),
                "checkpoint": "\n".join(
                    f"- Ask yourself: {point}" for point in concept_points[:3]
                ),
            },
            {
                "id": "example",
                "title": "Real World Example",
                "kind": "example",
                "content": (
                    f"{real_world}\n\n"
                    f"Teacher move: I will not jump to the formula. First I translate the story:\n"
                    f"{example}\n\n"
                    "Socratic check: if one value changes, which part of your setup changes and which part stays fixed?"
                ),
                "checkpoint": "Say the setup aloud once. If the setup is right, calculation becomes the easy part.",
            },
            {
                "id": "trick",
                "title": "Exam Trick",
                "kind": "shortcut",
                "content": (
                    f"Shortcut for {topic_name}: {trick}\n\n"
                    "Use it only after the setup is clear. Shortcuts are powerful when they reduce work, "
                    "not when they hide confusion."
                ),
                "checkpoint": (
                    "Speed rule: if you cannot explain the shortcut in one sentence, use the full method once."
                ),
            },
            {
                "id": "guided-practice",
                "title": "Your Turn",
                "kind": "practice",
                "content": (
                    f"{material.get('practice_prompt') or 'Try one question before the quiz.'}\n\n"
                    "I want you to solve it in three beats: setup, method, option check."
                ),
                "checkpoint": (
                    "Write: Given -> Asked -> Method -> Final option. This tiny structure prevents most silly mistakes."
                ),
            },
            {
                "id": "recap",
                "title": "Lock It In",
                "kind": "recap",
                "content": (
                    f"One-line memory: {material.get('recap') or trick}\n\n"
                    f"Your quiz mindset: {'accuracy first, speed second' if extra_focus else 'steady speed with a final option check'}."
                ),
                "checkpoint": "\n".join(f"- Avoid: {mistake}" for mistake in mistakes[:3]),
            },
        ]
    )
    return steps


def _socratic_question(topic_name: str) -> str:
    lowered = topic_name.lower()
    if "percentage" in lowered:
        return "what is the original base value, and what changed from it?"
    if "profit" in lowered or "loss" in lowered:
        return "are you comparing with cost price or selling price?"
    if "ratio" in lowered:
        return "what does one part represent before you scale the ratio?"
    if "time" in lowered and "work" in lowered:
        return "what fraction of work is completed in one unit of time?"
    if "speed" in lowered or "distance" in lowered:
        return "which two of speed, time, and distance are directly given?"
    if "series" in lowered:
        return "are the gaps changing, multiplying, or alternating?"
    if "coding" in lowered:
        return "is the code shifting letters, reversing order, or replacing symbols?"
    if "blood" in lowered:
        return "whose relation to whom is being asked?"
    if "direction" in lowered:
        return "where is the starting point, and what is the final displacement?"
    if "syllogism" in lowered:
        return "which conclusion must always be true, not just possibly true?"
    return "what is given, what is asked, and what pattern connects them?"


def _real_world_example(topic_name: str) -> str:
    lowered = topic_name.lower()
    if "percentage" in lowered:
        return "Real life: a shop gives 20% off on a phone. The first question is not the discount amount; it is the price the 20% is taken from."
    if "profit" in lowered or "loss" in lowered:
        return "Real life: a seller buys headphones for one price and sells them for another. Profit is judged against the buying price, not your feeling about the deal."
    if "ratio" in lowered:
        return "Real life: making lemonade in a 2:3 sugar-to-water ratio means every batch grows by parts, not by random spoon counts."
    if "time" in lowered and "work" in lowered:
        return "Real life: two people painting a room are not adding hours; they are adding rates of work per hour."
    if "speed" in lowered or "distance" in lowered:
        return "Real life: if a bus leaves late, speed, time, and distance decide whether it can still reach on schedule."
    if "series" in lowered:
        return "Real life: monthly savings can grow by a fixed amount or a multiplying pattern; spotting that pattern is number series."
    if "coding" in lowered:
        return "Real life: simple ciphers replace or shift letters. Competitive reasoning asks you to discover that hidden rule quickly."
    if "blood" in lowered:
        return "Real life: family introductions become easy when you draw a tiny family tree instead of holding all relations in memory."
    if "direction" in lowered:
        return "Real life: navigating streets works by tracking turns and final displacement from the starting point."
    if "syllogism" in lowered:
        return "Real life: if all managers are employees, you cannot conclude all employees are managers. Syllogism protects you from that trap."
    return f"Real life: {topic_name} becomes easier when you convert words into a small visual setup before calculating."


def _plain_lesson_content(steps: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        f"### {step['title']}\n{step.get('content', '')}\n{step.get('checkpoint') or ''}".strip()
        for step in steps
    )


def teach_plan_day(plan_day_id: str, user_id: str) -> dict[str, Any]:
    found = get_plan_by_day(plan_day_id)
    if not found:
        raise ValueError("Plan day not found")
    plan, day = found
    _ensure_user(user_id, level=plan.get("level", "beginner"), exam_id=plan.get("exam_id"))

    topic = _topic_map([day["topic_id"]]).get(day["topic_id"])
    material = _lesson_material(day["topic_id"])
    if not topic:
        raise ValueError("This lesson is not ready yet.")
    knowledge = None
    if plan.get("exam_id") == EXTERNAL_FOUNDATION_EXAM_ID:
        knowledge = external_knowledge_for_topic(topic["topic_name"], topic.get("subject"))
    if not material:
        knowledge = knowledge or external_knowledge_for_topic(topic["topic_name"], topic.get("subject"))
        material = _knowledge_material(topic, knowledge)
        _safe_upsert("topic_lesson_material", material, on_conflict="id")

    personalization = _adaptive_context(user_id, day["topic_id"], int(day.get("difficulty") or 3))
    personalization["level"] = plan.get("level", "beginner")
    personalization["user_goal"] = (plan.get("meta") or {}).get("user_goal", "")
    revision_id = (day.get("revision_topic_ids") or [None])[0]
    revision = _revision_for_topic(revision_id)
    steps = _build_lesson_steps(topic, material, revision, personalization)
    content = _plain_lesson_content(steps)
    taught_at = datetime.now().isoformat(timespec="seconds")
    _table("study_plan_days").update({"status": "taught", "taught_at": taught_at}).eq("id", plan_day_id).execute()
    log_id = _new_id("log")
    _table("teaching_logs").insert(
        {
            "id": log_id,
            "plan_day_id": plan_day_id,
            "user_id": user_id,
            "topic_id": day["topic_id"],
            "content_summary": content,
            "revision_covered": [revision_id] if revision_id else [],
            "llm_trace": {
                "teacher_flow": ["profile", "plan_day", "topic", "external_knowledge", "revision", "lesson_steps"],
                "personalization": personalization,
                "knowledge_sources": (knowledge or {}).get("sources", []),
                "hidden_from_learner": True,
            },
            "duration_mins": day.get("allocated_minutes", 90),
        }
    ).execute()
    return {
        "log_id": log_id,
        "lesson_content": content,
        "lesson_steps": steps,
        "revision": revision,
        "teacher_status": "complete",
        "topic_name": day["topic_name"],
        "status": "taught",
        "personalization": personalization,
    }


def _quiz_templates(topic_id: str, num_questions: int, difficulty: int) -> list[dict[str, Any]]:
    rows = _data(
        _table("quiz_templates")
        .select("*")
        .eq("topic_id", topic_id)
        .eq("is_active", True)
        .execute()
    )
    if not rows:
        return []
    rows.sort(key=lambda row: abs(int(row.get("difficulty") or difficulty) - difficulty))
    requested = max(1, min(20, int(num_questions)))
    return rows[:requested]


def generate_quiz(
    user_id: str,
    topic_id: str,
    num_questions: int = 5,
    difficulty: int = 3,
    plan_day_id: str | None = None,
) -> dict[str, Any]:
    topic = _topic_map([topic_id]).get(topic_id)
    if not topic:
        raise ValueError("This quiz is not ready yet.")
    adaptive = _adaptive_context(user_id, topic_id, difficulty)
    templates = _quiz_templates(topic_id, num_questions, int(adaptive["adapted_difficulty"]))
    if not templates:
        knowledge = external_knowledge_for_topic(topic["topic_name"], topic.get("subject"))
        templates = _knowledge_quiz_templates(topic, knowledge)
        for template in templates:
            _safe_upsert("quiz_templates", template, on_conflict="id")
    random.shuffle(templates)
    questions = []
    requested = max(1, min(20, int(num_questions)))
    for template in templates[:requested]:
        body = template.get("template_body") or {}
        answer_key = template.get("answer_key") or {}
        questions.append(
            {
                "template_id": template["id"],
                "question_text": body.get("question_text", ""),
                "options": body.get("options") or [],
                "correct_index": int(answer_key.get("correct_index", 0)),
                "explanation": answer_key.get("explanation", ""),
            }
        )
    attempt_id = _new_id("attempt")
    _table("quiz_attempts").insert(
        {
            "id": attempt_id,
            "user_id": user_id,
            "topic_id": topic_id,
            "plan_day_id": plan_day_id,
            "template_id": questions[0].get("template_id"),
            "questions": questions,
            "total_questions": len(questions),
            "difficulty": int(adaptive["adapted_difficulty"]),
            "adaptive_context": adaptive,
        }
    ).execute()
    return {
        "attempt_id": attempt_id,
        "questions": [{"question_text": q["question_text"], "options": q["options"]} for q in questions],
        "total": len(questions),
        "adaptive_context": adaptive,
    }


def _top_weaknesses(user_id: str) -> list[dict[str, Any]]:
    rows = _data(
        _table("user_performance")
        .select("*")
        .eq("user_id", user_id)
        .order("weakness_score", desc=True)
        .limit(10)
        .execute()
    )
    topics = _topic_map([row["topic_id"] for row in rows])
    return [
        {
            "topic_id": row["topic_id"],
            "topic_name": topics.get(row["topic_id"], {}).get("topic_name", row["topic_id"]),
            "weakness_score": float(row.get("weakness_score") or 50.0),
            "rank": index + 1,
            "recommended_extra_mins": 20 if float(row.get("weakness_score") or 0) >= 60 else 0,
        }
        for index, row in enumerate(rows)
    ]


def submit_quiz(attempt_id: str, user_answers: list[int], time_taken_secs: int) -> dict[str, Any]:
    attempt = _one(_table("quiz_attempts").select("*").eq("id", attempt_id).limit(1).execute())
    if not attempt:
        raise ValueError("Attempt not found")
    questions = attempt["questions"]
    results = [
        index < len(user_answers) and int(user_answers[index]) == int(question["correct_index"])
        for index, question in enumerate(questions)
    ]
    total = len(questions)
    score = sum(results)
    accuracy = round(score * 100 / total, 2) if total else 0.0
    submitted_at = datetime.now().isoformat(timespec="seconds")
    _table("quiz_attempts").update(
        {
            "user_answers": user_answers,
            "score": score,
            "accuracy": accuracy,
            "time_taken_secs": time_taken_secs,
            "submitted_at": submitted_at,
        }
    ).eq("id", attempt_id).execute()

    user_id = attempt["user_id"]
    topic_id = attempt["topic_id"]
    current = _one(
        _table("user_performance")
        .select("*")
        .eq("user_id", user_id)
        .eq("topic_id", topic_id)
        .limit(1)
        .execute()
    )
    attempts = int((current or {}).get("attempts") or 0) + total
    correct = int((current or {}).get("correct") or 0) + score
    updated_accuracy = round(correct * 100 / attempts, 2) if attempts else 0.0
    new_weakness_score = round((1 - updated_accuracy / 100) * 70 + 9, 2)
    perf = {
        "id": (current or {}).get("id") or _new_id("perf"),
        "user_id": user_id,
        "topic_id": topic_id,
        "attempts": attempts,
        "correct": correct,
        "accuracy": updated_accuracy,
        "avg_time_secs": round(time_taken_secs / total, 2) if total else 0,
        "weakness_score": new_weakness_score,
        "last_attempted": submitted_at,
    }
    _table("user_performance").upsert(perf, on_conflict="user_id,topic_id").execute()

    passed = accuracy >= PASS_MARK
    replan_triggered = not passed
    next_day_unlocked = False
    if passed and attempt.get("plan_day_id"):
        found = get_plan_by_day(attempt["plan_day_id"])
        if found:
            plan, day = found
            next_day_unlocked = any(
                item["day_number"] == int(day["day_number"]) + 1 and item["unlocked"]
                for item in plan["days"]
            )
    elif replan_triggered and attempt.get("plan_day_id"):
        found = get_plan_by_day(attempt["plan_day_id"])
        if found:
            plan, _day = found
            meta = plan.get("meta") or {}
            meta.update(
                {
                    "replan_flag": True,
                    "replan_reason": "quiz_below_pass_mark",
                    "affected_topics": [topic_id],
                    "flagged_at": submitted_at,
                    "latest_accuracy": accuracy,
                }
            )
            _table("study_plans").update({"meta": meta}).eq("id", plan["id"]).execute()

    return {
        "score": score,
        "total": total,
        "accuracy": accuracy,
        "per_question_result": results,
        "updated_accuracy": updated_accuracy,
        "new_weakness_score": new_weakness_score,
        "replan_triggered": replan_triggered,
        "top_weak_topics": _top_weaknesses(user_id),
        "passed": passed,
        "pass_mark": PASS_MARK,
        "next_day_unlocked": next_day_unlocked,
        "recommended_action": "continue" if passed else "revise",
    }


def get_user_profile(user_id: str) -> dict[str, Any]:
    user = _one(_table("users").select("*").eq("id", user_id).limit(1).execute())
    if not user:
        raise ValueError("User profile not found")
    plan = get_active_plan(user_id)
    progress = get_progress(user_id)
    return {
        "user": user,
        "active_plan": plan,
        "progress": progress,
        "source": "supabase",
    }


def _parse_day(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _month_bounds(today: date) -> tuple[date, date]:
    start = today.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _level_from_points(points: int) -> dict[str, Any]:
    level = max(1, points // 120 + 1)
    current_floor = (level - 1) * 120
    next_floor = level * 120
    progress = round(((points - current_floor) / 120) * 100, 1)
    return {
        "points": points,
        "level": level,
        "title": "Rookie" if level < 3 else "Builder" if level < 6 else "Mastery",
        "current_level_points": current_floor,
        "next_level_points": next_floor,
        "progress_percent": progress,
    }


def _activity_badges(
    total_questions: int,
    total_correct: int,
    active_days: int,
    best_streak: int,
    topic_stats: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    avg_accuracy = round(total_correct * 100 / total_questions, 2) if total_questions else 0
    badge_defs = [
        ("first-quiz", "First Quiz", "Complete one Supabase-saved quiz.", total_questions > 0),
        ("sharp-70", "70% Sharp", "Reach 70% overall accuracy.", avg_accuracy >= 70),
        ("streak-3", "3 Day Streak", "Practice on three days in a row.", best_streak >= 3),
        ("hundred", "100 Questions", "Try 100 saved questions.", total_questions >= 100),
        ("topic-clear", "Topic Clear", "Score 80% or more in any topic.", any(topic["accuracy"] >= 80 for topic in topic_stats)),
        ("steady", "Steady Learner", "Practice on five days this month.", active_days >= 5),
    ]
    return [
        {
            "id": badge_id,
            "name": name,
            "description": description,
            "earned": earned,
        }
        for badge_id, name, description, earned in badge_defs
    ]


def _activity_profile(user_id: str, topic_stats: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _data(
        _table("quiz_attempts")
        .select("id,score,total_questions,accuracy,submitted_at,attempted_at")
        .eq("user_id", user_id)
        .order("attempted_at", desc=False)
        .execute()
    )
    today = date.today()
    month_start, month_end = _month_bounds(today)
    month_days = (month_end - month_start).days
    daily: dict[str, dict[str, Any]] = {
        (month_start + timedelta(days=offset)).isoformat(): {
            "date": (month_start + timedelta(days=offset)).isoformat(),
            "label": (
                f"{(month_start + timedelta(days=offset)).strftime('%b')} "
                f"{(month_start + timedelta(days=offset)).day}"
            ),
            "attempts": 0,
            "questions": 0,
            "correct": 0,
            "accuracy": 0.0,
            "points": 0,
            "level": 0,
            "is_current_month": True,
        }
        for offset in range(month_days)
    }
    total_questions = 0
    total_correct = 0
    active_dates: set[date] = set()
    for row in rows:
        attempted_day = _parse_day(row.get("submitted_at"))
        if not attempted_day:
            continue
        questions = int(row.get("total_questions") or 0)
        correct = int(row.get("score") or 0)
        total_questions += questions
        total_correct += correct
        active_dates.add(attempted_day)
        key = attempted_day.isoformat()
        if key not in daily:
            continue
        cell = daily[key]
        cell["attempts"] += 1
        cell["questions"] += questions
        cell["correct"] += correct
        cell["points"] += correct * 10 + max(0, questions - correct) * 2
        cell["accuracy"] = round(cell["correct"] * 100 / cell["questions"], 2) if cell["questions"] else 0.0
        cell["level"] = 1 if cell["points"] < 30 else 2 if cell["points"] < 80 else 3 if cell["points"] < 140 else 4

    sorted_dates = sorted(active_dates)
    current_streak = 0
    cursor = today
    while cursor in active_dates:
        current_streak += 1
        cursor -= timedelta(days=1)
    best_streak = 0
    running = 0
    previous: date | None = None
    for active_day in sorted_dates:
        running = running + 1 if previous and active_day == previous + timedelta(days=1) else 1
        best_streak = max(best_streak, running)
        previous = active_day

    total_points = total_correct * 10 + max(0, total_questions - total_correct) * 2
    active_days_this_month = sum(1 for cell in daily.values() if cell["attempts"] > 0)
    return {
        "month": month_start.strftime("%B %Y"),
        "heatmap": list(daily.values()),
        "points": _level_from_points(total_points),
        "streak": {
            "current": current_streak,
            "best": best_streak,
            "active_days_this_month": active_days_this_month,
        },
        "badges": _activity_badges(
            total_questions,
            total_correct,
            active_days_this_month,
            best_streak,
            topic_stats,
        ),
    }


def get_progress(user_id: str) -> dict[str, Any]:
    rows = _data(
        _table("user_performance")
        .select("*")
        .eq("user_id", user_id)
        .order("weakness_score", desc=True)
        .execute()
    )
    topics = _topic_map([row["topic_id"] for row in rows])
    topic_stats = [
        {
            "topic_id": row["topic_id"],
            "topic_name": topics.get(row["topic_id"], {}).get("topic_name", row["topic_id"]),
            "attempts": int(row.get("attempts") or 0),
            "correct": int(row.get("correct") or 0),
            "accuracy": float(row.get("accuracy") or 0.0),
            "weakness_score": float(row.get("weakness_score") or 50.0),
        }
        for row in rows
    ]
    return {
        "topic_stats": topic_stats,
        "top_weaknesses": _top_weaknesses(user_id),
        "activity": _activity_profile(user_id, topic_stats),
    }


def replan_user(user_id: str) -> dict[str, Any]:
    active = get_active_plan(user_id)
    if not active:
        raise ValueError("No active plan to replan")
    weak_scores = _weak_scores(user_id)
    pending = [day for day in active["days"] if day["status"] == "pending"]
    pending.sort(key=lambda day: weak_scores.get(day["topic_id"], 0), reverse=True)
    pending_iter = iter(pending)
    updates = []
    for index, day in enumerate(active["days"]):
        if day["status"] != "pending":
            continue
        replacement = next(pending_iter)
        score = weak_scores.get(replacement["topic_id"], 0)
        previous_topic_id = active["days"][index - 1]["topic_id"] if index >= 1 else None
        updates.append(
            {
                "id": day["id"],
                "topic_id": replacement["topic_id"],
                "allocated_minutes": 110 if score >= 60 else 90,
                "revision_topic_ids": [previous_topic_id] if previous_topic_id else [],
            }
        )
    for update in updates:
        row_id = update.pop("id")
        _table("study_plan_days").update(update).eq("id", row_id).execute()
    meta = active.get("meta") or {}
    meta["replanned_at"] = datetime.now().isoformat(timespec="seconds")
    meta["pass_mark"] = PASS_MARK
    meta["planner_version"] = PLANNER_VERSION
    meta["workflow"] = "planner_update_loop"
    meta["pending_days_updated"] = len(updates)
    meta.pop("replan_flag", None)
    _table("study_plans").update({"meta": meta}).eq("id", active["id"]).execute()
    return {
        "updated_plan_id": active["plan_id"],
        "message": "Plan updated: remaining days adjusted for focus areas",
        "workflow": [
            {"step": "fetch_active_plan", "status": "complete", "plan_id": active["plan_id"]},
            {"step": "fetch_weak_areas", "status": "complete", "weak_topics": len(weak_scores)},
            {"step": "reorder_pending_days", "status": "complete", "pending_days": len(updates)},
            {"step": "update_plan_days", "status": "complete", "days_updated": len(updates)},
            {"step": "update_plan_meta", "status": "complete", "plan_id": active["plan_id"]},
        ],
    }
