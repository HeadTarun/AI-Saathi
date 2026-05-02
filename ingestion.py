"""
ingest_syllabus.py — AI Study Companion
========================================
Reads syllabus files from the data/ folder and populates:
  1. exams               — one row per exam (upsert)
  2. syllabus_topics     — one row per topic (upsert)
  3. embedding_vector    — pgvector column on syllabus_topics

Supported input formats
-----------------------
  data/
    ssc_cgl/
      quantitative_aptitude.md
      logical_reasoning.md
      english.md
      general_awareness.md
    sbi_po/
      quantitative_aptitude.md
      reasoning.md
      english.md

  Or a flat structure:
    data/
      SSC_CGL_Quantitative_Aptitude.md
      SBI_PO_Reasoning.md

  Also supports PDF files (text extracted via pdfplumber).

Markdown file format (one topic per ## heading)
------------------------------------------------
# SSC CGL — Quantitative Aptitude           ← optional file-level header (ignored)
# exam: SSC CGL                              ← optional exam override
# subject: Quantitative Aptitude            ← optional subject override
# syllabus_version: 2024                    ← optional, default "2024"

## Percentage                               ← topic name (required)
priority: HIGH                              ← HIGH / MED / LOW  (default MED)
difficulty: 2                               ← 1–5               (default 3)
estimated_hours: 3.5                        ← float             (default 2.0)
prerequisites: Fractions, Ratios            ← comma-separated topic names (resolved later)

Subtopics:
- Basic percentage calculation
- Percentage increase/decrease
- Successive percentage change
- Population-based problems

Description:
Percentage is one of the most fundamental topics in QA.
It forms the basis for Profit & Loss, Simple/Compound Interest,
and Data Interpretation. High weightage in Tier-I.

## Profit and Loss
priority: HIGH
...

Usage
-----
  # Dry run — parse files, show what would be inserted, don't touch DB
  python ingest_syllabus.py --dry-run

  # Full run with OpenAI embeddings (primary)
  python ingest_syllabus.py

  # Force re-embed all topics (even those that already have vectors)
  python ingest_syllabus.py --reembed

  # Use Ollama instead of OpenAI (768 dims — REQUIRES schema change to VECTOR(768))
  python ingest_syllabus.py --embedder ollama

  # Skip embedding entirely (populate topics table only)
  python ingest_syllabus.py --no-embed

  # Point to a different data directory
  python ingest_syllabus.py --data-dir ./my_syllabus

  # Target a specific exam only
  python ingest_syllabus.py --exam "SSC CGL"

  # After bulk insert, rebuild ivfflat index for fast similarity search
  python ingest_syllabus.py --rebuild-index

Environment variables (read from .env automatically)
-----------------------------------------------------
  OPENAI_API_KEY      — for text-embedding-ada-002 (1536 dims)
  GROQ_API_KEY        — not needed for ingestion
  postgres_host       — default: localhost
  postgres_port       — default: 5432
  postgres_user       — default: studyapp
  postgres_password   — default: studypass
  postgres_db         — default: study_companion
  OLLAMA_BASE_URL     — default: http://localhost:11434
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Lazy imports so the script can do --help without needing every dep installed
# ---------------------------------------------------------------------------

def _require(pkg: str, install_hint: str = "") -> None:
    try:
        __import__(pkg)
    except ImportError:
        hint = f"  pip install {install_hint or pkg}" 
        sys.exit(f"Missing dependency: {pkg}\n{hint}")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class TopicRecord:
    exam_name: str
    syllabus_version: str
    subject: str
    topic_name: str
    subtopics: list[str]
    difficulty: int
    priority: str
    estimated_hours: float
    prerequisite_names: list[str]          # resolved to IDs after insert
    description: str
    source_file: str

    # filled in after DB upsert
    exam_id: Optional[str] = None
    topic_id: Optional[str] = None
    embedding: Optional[list[float]] = None

    def embed_text(self) -> str:
        """Text sent to the embedding model — topic name + subtopics + description."""
        parts = [
            f"Topic: {self.topic_name}",
            f"Subject: {self.subject}",
            f"Exam: {self.exam_name}",
        ]
        if self.subtopics:
            parts.append("Subtopics: " + ", ".join(self.subtopics))
        if self.description:
            parts.append(self.description.strip())
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Parser — reads .md and .pdf files
# ---------------------------------------------------------------------------

_PRIORITY_VALUES = {"HIGH", "MED", "LOW"}
_KV_RE = re.compile(r"^(priority|difficulty|estimated_hours|prerequisites)\s*[:=]\s*(.+)$", re.I)


def _parse_md_file(path: Path) -> list[TopicRecord]:
    """Parse a markdown syllabus file into TopicRecord list."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # ---- File-level metadata from # directives ----
    exam_name = _guess_exam_from_path(path)
    subject = _guess_subject_from_path(path)
    syllabus_version = "2024"

    for line in lines[:20]:
        m = re.match(r"^#\s+exam\s*[:=]\s*(.+)", line, re.I)
        if m:
            exam_name = m.group(1).strip()
        m = re.match(r"^#\s+subject\s*[:=]\s*(.+)", line, re.I)
        if m:
            subject = m.group(1).strip()
        m = re.match(r"^#\s+syllabus_version\s*[:=]\s*(.+)", line, re.I)
        if m:
            syllabus_version = m.group(1).strip()

    # ---- Split by ## topic headings ----
    records: list[TopicRecord] = []
    current_topic: Optional[str] = None
    current_lines: list[str] = []

    def flush():
        nonlocal current_topic, current_lines
        if current_topic:
            rec = _parse_topic_block(
                topic_name=current_topic,
                block_lines=current_lines,
                exam_name=exam_name,
                subject=subject,
                syllabus_version=syllabus_version,
                source_file=str(path),
            )
            if rec:
                records.append(rec)
        current_topic = None
        current_lines = []

    for line in lines:
        if line.startswith("## "):
            flush()
            current_topic = line[3:].strip()
        elif current_topic is not None:
            current_lines.append(line)

    flush()
    return records


def _parse_topic_block(
    topic_name: str,
    block_lines: list[str],
    exam_name: str,
    subject: str,
    syllabus_version: str,
    source_file: str,
) -> Optional[TopicRecord]:
    """Parse key-value metadata and subtopics from a ## block."""
    difficulty = 3
    priority = "MED"
    estimated_hours = 2.0
    prerequisite_names: list[str] = []
    subtopics: list[str] = []
    description_lines: list[str] = []

    mode = "meta"  # meta → subtopics → description

    for line in block_lines:
        stripped = line.strip()

        if re.match(r"^subtopics\s*:", stripped, re.I):
            mode = "subtopics"
            continue
        if re.match(r"^description\s*:", stripped, re.I):
            mode = "description"
            continue

        if mode == "meta":
            m = _KV_RE.match(stripped)
            if m:
                key, val = m.group(1).lower(), m.group(2).strip()
                if key == "priority":
                    priority = val.upper() if val.upper() in _PRIORITY_VALUES else "MED"
                elif key == "difficulty":
                    try:
                        difficulty = max(1, min(5, int(val)))
                    except ValueError:
                        pass
                elif key == "estimated_hours":
                    try:
                        estimated_hours = float(val)
                    except ValueError:
                        pass
                elif key == "prerequisites":
                    prerequisite_names = [p.strip() for p in val.split(",") if p.strip()]

        elif mode == "subtopics":
            if stripped.startswith("- "):
                subtopics.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("#"):
                subtopics.append(stripped)

        elif mode == "description":
            if stripped:
                description_lines.append(stripped)

    return TopicRecord(
        exam_name=exam_name,
        syllabus_version=syllabus_version,
        subject=subject,
        topic_name=topic_name,
        subtopics=subtopics,
        difficulty=difficulty,
        priority=priority,
        estimated_hours=estimated_hours,
        prerequisite_names=prerequisite_names,
        description=" ".join(description_lines),
        source_file=source_file,
    )


def _parse_pdf_file(path: Path) -> list[TopicRecord]:
    """Extract text from PDF and parse as markdown (best-effort)."""
    _require("pdfplumber", "pdfplumber")
    import pdfplumber  # type: ignore

    text_parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)

    if not text_parts:
        print(f"  [warn] No text extracted from {path.name} — skipping")
        return []

    # Write to a temp .md file and parse
    tmp = path.with_suffix(".extracted.md")
    tmp.write_text("\n".join(text_parts), encoding="utf-8")
    try:
        records = _parse_md_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)
    return records


def _guess_exam_from_path(path: Path) -> str:
    """Infer exam name from directory or filename."""
    parent = path.parent.name.lower()
    name = path.stem.lower()

    if "ssc_cgl" in parent or "ssc_cgl" in name:
        return "SSC CGL"
    if "ssc" in parent or "ssc" in name:
        return "SSC CGL"
    if "sbi_po" in parent or "sbi_po" in name:
        return "SBI PO"
    if "sbi" in parent or "sbi" in name:
        return "SBI PO"
    if "banking" in parent or "banking" in name:
        return "SBI PO"
    # Use directory name as fallback — pretty-print it
    return parent.replace("_", " ").title() if parent != "data" else "SSC CGL"


def _guess_subject_from_path(path: Path) -> str:
    """Infer subject from filename."""
    name = path.stem.lower()
    if "quant" in name or "mathematics" in name or "maths" in name:
        return "Quantitative Aptitude"
    if "reason" in name or "logical" in name or "logic" in name:
        return "Logical Reasoning"
    if "english" in name or "verbal" in name:
        return "English"
    if "general" in name or "awareness" in name or "gk" in name:
        return "General Awareness"
    if "computer" in name:
        return "Computer Aptitude"
    return "Quantitative Aptitude"


# ---------------------------------------------------------------------------
# Embedder
# ---------------------------------------------------------------------------

class OpenAIEmbedder:
    DIM = 1536
    MODEL = "text-embedding-ada-002"

    def __init__(self, api_key: str):
        _require("openai", "openai")
        from openai import AsyncOpenAI  # type: ignore
        self._client = AsyncOpenAI(api_key=api_key)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed up to 100 texts at once (OpenAI limit)."""
        # Rate-limit: 3500 RPM on free tier → batch to avoid 429s
        results: list[list[float]] = []
        batch_size = 20
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            resp = await self._client.embeddings.create(input=batch, model=self.MODEL)
            results.extend([d.embedding for d in sorted(resp.data, key=lambda x: x.index)])
            if i + batch_size < len(texts):
                await asyncio.sleep(0.5)  # gentle rate limit
        return results


class OllamaEmbedder:
    """Uses nomic-embed-text — 768 dims.
    IMPORTANT: only use this if you change the schema to VECTOR(768).
    and re-run the migration.
    """
    DIM = 768
    MODEL = "nomic-embed-text"

    def __init__(self, base_url: str = "http://localhost:11434"):
        _require("httpx")
        self._base_url = base_url.rstrip("/")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import httpx  # type: ignore
        results = []
        async with httpx.AsyncClient(timeout=60) as client:
            for text in texts:
                resp = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self.MODEL, "prompt": text},
                )
                resp.raise_for_status()
                results.append(resp.json()["embedding"])
        return results


class HuggingFaceEmbedder:
    """
    Local embedder using sentence-transformers.
    No API key required. Runs on CPU or GPU.

    Recommended model: BAAI/bge-large-en-v1.5 (1024 dims).
    Schema must have VECTOR(1024).
    """

    def __init__(self, model_name: str = "BAAI/bge-large-en-v1.5"):
        _require("sentence_transformers", "sentence-transformers")
        from sentence_transformers import SentenceTransformer  # type: ignore

        print(f"  Loading model {model_name} (first run may download it)...")
        self._model = SentenceTransformer(model_name)
        self.DIM = self._model.get_sentence_embedding_dimension()
        print(f"  Model loaded. Embedding dim: {self.DIM}")

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Encode texts without blocking the event loop."""
        loop = asyncio.get_event_loop()

        def _encode():
            embeddings = self._model.encode(
                texts,
                batch_size=32,
                show_progress_bar=len(texts) > 10,
                normalize_embeddings=True,
            )
            return embeddings.tolist()

        return await loop.run_in_executor(None, _encode)


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

async def _get_conn(args):
    _require("asyncpg")
    import asyncpg  # type: ignore

    host = os.environ.get("postgres_host", "localhost")
    port = int(os.environ.get("postgres_port", 5432))
    user = os.environ.get("postgres_user", "studyapp")
    password = os.environ.get("postgres_password", "studypass")
    db = os.environ.get("postgres_db", "study_companion")

    return await asyncpg.connect(
        host=host, port=port, user=user, password=password, database=db
    )


async def upsert_exam(conn, exam_name: str, syllabus_version: str) -> str:
    """Insert or update exam, return its UUID."""
    row = await conn.fetchrow(
        """
        INSERT INTO exams (name, syllabus_version, description, is_active)
        VALUES ($1, $2, $3, true)
        ON CONFLICT (name) DO UPDATE
            SET syllabus_version = EXCLUDED.syllabus_version,
                is_active = true
        RETURNING id::text
        """,
        exam_name,
        syllabus_version,
        f"Indian competitive exam: {exam_name}",
    )
    return row["id"]


async def upsert_topic(conn, rec: TopicRecord) -> str:
    """Insert or update a syllabus topic, return its UUID."""
    row = await conn.fetchrow(
        """
        INSERT INTO syllabus_topics
            (exam_id, subject, topic_name, subtopics, difficulty, priority,
             estimated_hours)
        VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
        ON CONFLICT DO NOTHING
        RETURNING id::text
        """,
        rec.exam_id,
        rec.subject,
        rec.topic_name,
        rec.subtopics,
        rec.difficulty,
        rec.priority,
        rec.estimated_hours,
    )
    if row:
        return row["id"]
    # Already exists — fetch id
    existing = await conn.fetchval(
        """
        SELECT id::text FROM syllabus_topics
        WHERE exam_id = $1::uuid AND topic_name = $2
        LIMIT 1
        """,
        rec.exam_id,
        rec.topic_name,
    )
    return existing


async def update_embedding(conn, topic_id: str, embedding: list[float]) -> None:
    """Write embedding vector to the topic row."""
    # asyncpg doesn't know about pgvector natively — cast via SQL string
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    await conn.execute(
        """
        UPDATE syllabus_topics
        SET embedding_vector = $1::vector
        WHERE id = $2::uuid
        """,
        vec_str,
        topic_id,
    )


async def resolve_prerequisites(conn, records: list[TopicRecord]) -> None:
    """Update prerequisite_ids on each topic row using resolved name→id map."""
    # Build name → id map for all topics we just inserted
    name_to_id: dict[str, str] = {}
    for rec in records:
        if rec.topic_id:
            name_to_id[rec.topic_name.lower()] = rec.topic_id

    for rec in records:
        if not rec.prerequisite_names or not rec.topic_id:
            continue
        prereq_ids = [
            name_to_id[n.lower()]
            for n in rec.prerequisite_names
            if n.lower() in name_to_id
        ]
        if prereq_ids:
            await conn.execute(
                """
                UPDATE syllabus_topics
                SET prerequisite_ids = $1::uuid[]
                WHERE id = $2::uuid
                """,
                prereq_ids,
                rec.topic_id,
            )


async def rebuild_ivfflat_index(conn) -> None:
    """
    Drop and recreate the ivfflat index after bulk inserts.
    ivfflat needs at least 100 rows to build; skips if too few.
    """
    count = await conn.fetchval(
        "SELECT COUNT(*) FROM syllabus_topics WHERE embedding_vector IS NOT NULL"
    )
    if count < 10:
        print(f"  [skip] Only {count} embedded topics — ivfflat needs ≥100 for optimal performance. Index not rebuilt.")
        return

    print(f"  Rebuilding ivfflat index on {count} vectors…")
    await conn.execute("DROP INDEX IF EXISTS idx_syllabus_embedding")
    lists = max(4, count // 10)  # rule of thumb: sqrt(rows), min 4
    await conn.execute(
        f"""
        CREATE INDEX idx_syllabus_embedding
        ON syllabus_topics USING ivfflat (embedding_vector vector_cosine_ops)
        WITH (lists = {lists})
        """
    )
    print(f"  ✓ Index rebuilt with lists={lists}")


# ---------------------------------------------------------------------------
# Sample syllabus generator (creates data/ files if folder is empty)
# ---------------------------------------------------------------------------

SSC_CGL_QA = """\
# exam: SSC CGL
# subject: Quantitative Aptitude
# syllabus_version: 2024

## Percentage
priority: HIGH
difficulty: 2
estimated_hours: 3.5
prerequisites: Fractions, Ratios and Proportions

Subtopics:
- Basic percentage calculation
- Percentage increase and decrease
- Successive percentage change
- Population-based percentage problems
- Percentage error and approximation

Description:
Percentage is a foundational topic in Quantitative Aptitude. It appears directly
and as a base concept in Profit & Loss, Simple Interest, Compound Interest, and
Data Interpretation. 3-4 questions appear in SSC CGL Tier-I every year.

## Profit and Loss
priority: HIGH
difficulty: 3
estimated_hours: 4.0
prerequisites: Percentage

Subtopics:
- Cost price, selling price, marked price
- Profit and loss percentage
- Discount and successive discount
- Dishonest dealings and faulty weights
- Partnership-based profit sharing

Description:
Profit and Loss is one of the highest-weightage topics in SSC CGL. Builds directly
on Percentage. Questions range from straightforward SP/CP calculations to
multi-step discount chains and faulty-weight problems.

## Simple Interest
priority: HIGH
difficulty: 2
estimated_hours: 2.5
prerequisites: Percentage

Subtopics:
- SI formula and derivations
- Finding rate, time, or principal
- Difference between SI and CI
- Mixed problems with installments

Description:
Simple Interest questions in SSC CGL are usually direct formula applications.
Focus on SI-CI difference problems which are common in Tier-I.

## Compound Interest
priority: HIGH
difficulty: 3
estimated_hours: 3.0
prerequisites: Simple Interest, Percentage

Subtopics:
- CI formula annual, half-yearly, quarterly
- Difference between SI and CI for 2 and 3 years
- Population growth and depreciation
- Effective annual rate

Description:
Compound Interest requires understanding of exponential growth. The SI-CI
difference formula is a must-memorize shortcut for SSC CGL.

## Time and Work
priority: HIGH
difficulty: 3
estimated_hours: 4.0

Subtopics:
- Basic time and work formula
- Pipes and cisterns
- Efficiency-based problems
- MDH (Men-Days-Hours) formula
- Work and wages

Description:
Time and Work is consistently asked in SSC CGL Tier-I and Tier-II. The LCM
method (assigning total work as LCM of days) is the fastest approach and
should be the primary strategy.

## Speed, Distance and Time
priority: HIGH
difficulty: 3
estimated_hours: 3.5

Subtopics:
- Basic SDT formula and unit conversion
- Average speed problems
- Relative speed (same and opposite direction)
- Trains, boats and streams
- Circular track problems

Description:
SDT is a vast topic that covers trains, boats, streams, and circular tracks.
Each sub-type has unique formula patterns. Relative speed concept is key.

## Ratio and Proportions
priority: MED
difficulty: 2
estimated_hours: 2.0

Subtopics:
- Basic ratios and equivalent ratios
- Compound ratio
- Proportion and continued proportion
- Direct and inverse proportion
- Ratio-based mixture and alligation basics

Description:
Ratios are the foundation for many other topics. Keep this lightweight —
1-2 direct questions per exam. Focus on mixtures and alligation which combine
ratios with percentage.

## Average
priority: MED
difficulty: 2
estimated_hours: 2.0
prerequisites: Ratio and Proportions

Subtopics:
- Simple average formula
- Weighted average
- Average of consecutive numbers
- Change in average when a value is added or removed

Description:
Averages are straightforward. 1-2 questions in Tier-I. The shortcut of tracking
change in average (not recalculating from scratch) saves time.

## Number System
priority: MED
difficulty: 4
estimated_hours: 4.0

Subtopics:
- Natural, whole, integer, rational numbers
- Divisibility rules (2 through 13)
- HCF and LCM
- Prime factorization
- Remainder theorem and cyclicity
- Unit digit problems

Description:
Number System is concept-heavy and foundational. HCF/LCM and remainder problems
are regular features. Cyclicity (unit digit patterns) is frequently tested.

## Fractions
priority: MED
difficulty: 2
estimated_hours: 1.5

Subtopics:
- Types of fractions
- Comparison of fractions
- Operations on fractions
- Simplification

Description:
Fractions appear mostly in simplification questions and as prerequisites to
Percentage and Ratio problems. Keep this brief in the curriculum.

## Data Interpretation
priority: HIGH
difficulty: 4
estimated_hours: 5.0
prerequisites: Percentage, Average, Ratio and Proportions

Subtopics:
- Bar graphs
- Line graphs
- Pie charts
- Tables and caselets
- Mixed DI sets

Description:
Data Interpretation carries very high weightage in Tier-II (15-20 questions).
It tests speed of calculation and ability to read charts. Practice with
real SSC previous year DI sets. Focus on percentage-based DI first.

## Geometry
priority: MED
difficulty: 4
estimated_hours: 5.0

Subtopics:
- Lines, angles, triangles
- Congruency and similarity
- Circle theorems (tangent, chord, arc)
- Quadrilaterals and polygons
- Area and perimeter formulas

Description:
Geometry is a major topic in SSC CGL Tier-I (4-5 questions). Circle theorems
and triangle properties are the most tested. Focus on standard theorems and
their direct application rather than proofs.

## Mensuration
priority: HIGH
difficulty: 3
estimated_hours: 4.0
prerequisites: Geometry

Subtopics:
- Area and perimeter of 2D shapes
- Surface area and volume of 3D shapes
- Cube, cuboid, cylinder, cone, sphere
- Frustum and hollow cylinders
- Combined solids

Description:
Mensuration covers 2D and 3D geometry. 3D formulas (especially cones and
spheres) need memorization. Practice conversion between units.

## Trigonometry
priority: MED
difficulty: 4
estimated_hours: 4.0
prerequisites: Geometry

Subtopics:
- Basic trigonometric ratios
- Standard angles (0, 30, 45, 60, 90)
- Trigonometric identities
- Height and distance problems
- Complementary angles

Description:
Trigonometry in SSC CGL focuses on identities and height-distance problems.
Learn the identity sheet (sin²+cos²=1 family, 1+tan²=sec² family) and
all T-ratios for standard angles by heart.

## Algebra
priority: MED
difficulty: 3
estimated_hours: 3.5

Subtopics:
- Basic algebraic identities
- Linear and quadratic equations
- Polynomials and remainder theorem
- Surds and indices
- Linear equations in two variables

Description:
Algebra in SSC CGL is mostly identity-based. Substitution tricks (x+1/x=k
type problems) appear frequently. Focus on SSC-specific algebra patterns.
"""

SSC_CGL_LR = """\
# exam: SSC CGL
# subject: Logical Reasoning
# syllabus_version: 2024

## Series
priority: HIGH
difficulty: 3
estimated_hours: 3.0

Subtopics:
- Number series (missing term)
- Alphabet series
- Mixed series
- Wrong number in series
- Series based on squares and cubes

Description:
Series questions require identifying the pattern and finding the missing or
wrong term. Number series patterns include arithmetic, geometric, square/cube
progressions, and mixed patterns. MANDATORY template usage for quiz generation.

## Coding-Decoding
priority: HIGH
difficulty: 3
estimated_hours: 3.0

Subtopics:
- Letter coding
- Number coding
- Substitution coding
- Jumbled coding
- Coding by analogy

Description:
Coding-Decoding tests the ability to decode letter/number patterns.
Usually 3-4 questions in Tier-I. Newer exam patterns use table-based
coding which is more complex. MANDATORY template usage for quiz generation.

## Puzzles
priority: HIGH
difficulty: 4
estimated_hours: 5.0

Subtopics:
- Linear arrangement (single row)
- Circular arrangement
- Double row arrangement
- Floor/flat-based puzzles
- Day/month scheduling puzzles
- Comparison-based puzzles

Description:
Puzzles are the highest-weightage topic in the Reasoning section. Each puzzle
set typically has 4-5 questions. The key is systematic table-based solving.
MANDATORY template usage — never free-generate puzzle constraints.

## Seating Arrangement
priority: HIGH
difficulty: 4
estimated_hours: 4.0
prerequisites: Puzzles

Subtopics:
- Linear seating (facing same/opposite direction)
- Circular seating (facing centre / outside)
- Square and rectangular arrangements
- Mixed direction arrangements

Description:
Seating Arrangement is a special case of Puzzles. Circular arrangements with
mixed facing directions are the most complex. MANDATORY template usage.

## Direction Sense
priority: MED
difficulty: 3
estimated_hours: 2.5

Subtopics:
- Basic direction problems
- Shadow and sun-based directions
- Distance calculation
- Coordinate-based direction problems

Description:
Direction Sense tests spatial reasoning. Shadow-based questions (morning/evening
sun) have a specific logic that must be memorized. MANDATORY template usage.

## Blood Relations
priority: MED
difficulty: 3
estimated_hours: 2.5

Subtopics:
- Coded blood relations
- Family tree problems
- Mixed gender blood relations
- Pointing/introducing type problems

Description:
Blood Relations questions require building a family tree. The key challenge
is handling coded relations where parents/siblings are described indirectly.
MANDATORY template usage for quiz generation.

## Analogy
priority: MED
difficulty: 2
estimated_hours: 2.0

Subtopics:
- Word analogy (semantic)
- Number analogy
- Letter analogy
- GK-based analogy

Description:
Analogy tests the ability to identify relationships. SSC CGL uses word,
number, and letter analogies. 2-3 questions per exam.

## Classification
priority: MED
difficulty: 2
estimated_hours: 2.0

Subtopics:
- Odd one out (words)
- Odd one out (numbers)
- Odd one out (letters/pairs)

Description:
Classification (odd one out) is straightforward. The trick is identifying
the common property of 3 items and finding which one breaks the pattern.

## Syllogism
priority: MED
difficulty: 3
estimated_hours: 2.5

Subtopics:
- Two-statement syllogisms
- Three-statement syllogisms
- Complementary pairs
- Possibility-based conclusions

Description:
Syllogism requires Venn diagram reasoning. The 5-case Venn diagram approach
works for all standard syllogisms. Possibility questions are trickier —
a conclusion is possible if it's valid in at least one valid diagram.

## Input-Output
priority: MED
difficulty: 4
estimated_hours: 3.0

Subtopics:
- Word-based input-output
- Number-based input-output
- Mixed word-number series
- Step identification

Description:
Input-Output questions show a machine rearranging words/numbers across steps.
Find the pattern from the first 2-3 steps and extrapolate. MANDATORY template.

## Order and Ranking
priority: LOW
difficulty: 2
estimated_hours: 1.5

Subtopics:
- Position from left/right
- Rank from top/bottom
- Total number of people in a row
- Multiple criteria ranking

Description:
Order and Ranking is formula-based. Total = (Position from left) + (Position
from right) - 1. Easy marks — 1-2 questions per exam.

## Non-Verbal Reasoning
priority: MED
difficulty: 3
estimated_hours: 3.0

Subtopics:
- Mirror image
- Water image
- Figure series and pattern completion
- Paper folding and cutting
- Embedded figures
- Counting of figures

Description:
Non-verbal reasoning tests spatial visualization. Mirror/water image, figure
counting, and paper folding are regularly featured in SSC CGL Tier-I.
"""

SBI_PO_QA = """\
# exam: SBI PO
# subject: Quantitative Aptitude
# syllabus_version: 2024

## Data Interpretation
priority: HIGH
difficulty: 5
estimated_hours: 6.0
prerequisites: Percentage, Average, Ratio and Proportions

Subtopics:
- Caselet DI (paragraph-based)
- Mixed graph DI
- Pie chart with percentage
- Line and bar comparison
- Table-based complex DI
- Missing data DI

Description:
Data Interpretation is the single most important topic in SBI PO. 15 out of
35 questions in the mains quant section are DI. Caselets (paragraph DI) are
unique to banking exams and require careful reading alongside calculation.

## Quadratic Equations
priority: HIGH
difficulty: 2
estimated_hours: 2.0

Subtopics:
- Standard quadratic x² + bx + c = 0
- Comparison of roots (>, <, =, ≥, ≤)
- Factorization method
- Discriminant approach

Description:
Quadratic Equations is a high-scoring, low-effort topic in banking exams.
5 questions appear in almost every SBI PO prelims paper. Learn root-comparison
by factorization quickly.

## Number Series (Banking)
priority: HIGH
difficulty: 3
estimated_hours: 2.5

Subtopics:
- Wrong number series
- Missing number series
- Two-tier series
- Pattern-based series (prime, squares, cubes)

Description:
Banking number series tend to use two-tier and mixed patterns more than
SSC. 5 questions in prelims. Wrong number series (find the odd one out)
is more common in banking than in SSC.

## Percentage
priority: HIGH
difficulty: 2
estimated_hours: 2.5

Subtopics:
- Basic percentage calculation
- Percentage increase / decrease
- Successive discounts
- Population and depreciation percentage

Description:
Foundational topic that underlies DI, Profit & Loss, and SI/CI. In SBI PO
it appears mostly inside DI sets rather than as standalone questions.

## Simple and Compound Interest
priority: MED
difficulty: 3
estimated_hours: 2.5
prerequisites: Percentage

Subtopics:
- SI and CI formula
- SI vs CI difference (2 years and 3 years)
- Installment calculations
- Effective annual rate

Description:
SI/CI is less prominent in SBI PO than in SSC. Focus on the SI-CI difference
formula and installment-based problems which are favored in banking papers.

## Ratio and Proportions
priority: MED
difficulty: 2
estimated_hours: 1.5

Subtopics:
- Basic and compound ratios
- Partnerhsip problems
- Mixture and alligation
- Direct and inverse proportion

Description:
Ratio problems in banking often appear as partnership or mixture problems
embedded in DI caselets. Alligation (mixing two solutions) is tested directly.

## Probability
priority: MED
difficulty: 4
estimated_hours: 3.0

Subtopics:
- Classical probability (P = favorable/total)
- Conditional probability basics
- Complementary events
- Card, coin, dice problems
- Balls in a bag problems

Description:
Probability is tested in SBI PO mains. Card and ball problems are most common.
Focus on combinations approach for calculating favorable outcomes.

## Permutation and Combination
priority: MED
difficulty: 4
estimated_hours: 3.0

Subtopics:
- Fundamental counting principle
- Permutations (nPr)
- Combinations (nCr)
- Circular permutations
- Word formation problems
- Selection with restrictions

Description:
PnC is concept-heavy. Learn nCr and nPr formulas and when to use each.
Circular permutations (divide by n for identical rotations) and restricted
selections appear in SBI PO mains.
"""

SBI_PO_REASONING = """\
# exam: SBI PO
# subject: Logical Reasoning
# syllabus_version: 2024

## Puzzles
priority: HIGH
difficulty: 5
estimated_hours: 6.0

Subtopics:
- Floor-based puzzles (multi-attribute)
- Box stacking puzzles
- Month-date scheduling puzzles
- Parallel rows with multiple attributes
- Complex circular arrangements

Description:
Banking puzzles are significantly harder than SSC puzzles. Multi-attribute
puzzles (5 people × 3 attributes) are standard in SBI PO mains. 3-4 sets
of 4-5 questions each appear in every mains paper. MANDATORY template usage.

## Seating Arrangement
priority: HIGH
difficulty: 4
estimated_hours: 4.0
prerequisites: Puzzles

Subtopics:
- Circular with multiple attributes
- Double row facing each other
- Linear with uncertain positions
- Mixed arrangement with comparisons

Description:
SBI PO seating arrangements often combine circular/linear with additional
attributes (profession, city, floor). They require systematic grid-based
solving. MANDATORY template usage.

## Syllogism
priority: HIGH
difficulty: 3
estimated_hours: 2.5

Subtopics:
- Two and three-statement syllogisms
- Possibility conclusions
- All/Some/No pattern
- Reverse syllogism

Description:
Syllogism is a reliable 5-mark topic in SBI PO prelims. The Venn diagram
method is definitive. Possibility questions need careful treatment of the
'at least some' interpretation.

## Inequality
priority: HIGH
difficulty: 2
estimated_hours: 2.0

Subtopics:
- Direct inequality chains
- Coded inequality (substitution)
- Either-or conclusions
- Combined statements

Description:
Inequality is the easiest high-weightage topic in banking reasoning.
5 questions in prelims. Coded inequality just requires substituting
symbols back to their original operators before solving the chain.

## Direction Sense
priority: MED
difficulty: 3
estimated_hours: 2.0

Subtopics:
- Multi-turn direction problems
- Distance from starting point (Pythagoras)
- Blood relation combined with direction

Description:
Direction Sense in SBI PO is often combined with blood relations or
other topics. Distance calculation using Pythagoras theorem is essential.
MANDATORY template usage.

## Blood Relations
priority: MED
difficulty: 3
estimated_hours: 2.0

Subtopics:
- Coded blood relations
- Family tree with 3+ generations
- Mixed gender coded relations
- Puzzle-embedded blood relations

Description:
Blood relations appear both as standalone questions and embedded in puzzles.
SBI PO uses complex multi-generation family trees more than SSC.
MANDATORY template usage.

## Input-Output (Banking)
priority: MED
difficulty: 4
estimated_hours: 3.0

Subtopics:
- New pattern input-output (no fixed shift)
- Word and number rearrangement
- Step counting type
- Reverse step type

Description:
New-pattern input-output (introduced ~2016) has no fixed shift rule —
the arrangement changes based on the content of the words/numbers.
Requires careful step-by-step analysis. MANDATORY template usage.

## Data Sufficiency
priority: MED
difficulty: 4
estimated_hours: 3.0

Subtopics:
- Two-statement data sufficiency
- Three-statement data sufficiency
- Combined sufficiency
- Reasoning-based data sufficiency

Description:
Data Sufficiency tests whether given statements provide enough information
to answer a question — NOT whether you can actually solve it. This
conceptual distinction is key and frequently misunderstood.
"""


def _create_sample_files(data_dir: Path) -> None:
    """Write sample syllabus markdown files so the script has something to ingest."""
    files = {
        "ssc_cgl/quantitative_aptitude.md": SSC_CGL_QA,
        "ssc_cgl/logical_reasoning.md": SSC_CGL_LR,
        "sbi_po/quantitative_aptitude.md": SBI_PO_QA,
        "sbi_po/logical_reasoning.md": SBI_PO_REASONING,
    }
    for rel, content in files.items():
        p = data_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
            print(f"  Created sample: {p.relative_to(data_dir.parent)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)

    # ---- Load .env ----
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    # ---- Check / create sample data ----
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        print(f"data/ folder not found — creating sample syllabus files in {data_dir}/")
        _create_sample_files(data_dir)
    else:
        md_files = list(data_dir.rglob("*.md")) + list(data_dir.rglob("*.pdf"))
        if not md_files:
            print(f"No .md or .pdf files in {data_dir} — creating sample syllabus files.")
            _create_sample_files(data_dir)

    # ---- Discover files ----
    all_files = sorted(data_dir.rglob("*.md")) + sorted(data_dir.rglob("*.pdf"))
    if not all_files:
        sys.exit("No syllabus files found even after sample creation. Something is wrong.")

    print(f"\nFound {len(all_files)} syllabus file(s):")
    for f in all_files:
        print(f"  {f.relative_to(data_dir.parent)}")

    # ---- Parse ----
    records: list[TopicRecord] = []
    for f in all_files:
        if f.suffix == ".pdf":
            recs = _parse_pdf_file(f)
        else:
            recs = _parse_md_file(f)

        if args.exam and recs:
            recs = [r for r in recs if r.exam_name.lower() == args.exam.lower()]

        records.extend(recs)
        print(f"  Parsed {len(recs):>3} topics from {f.name}")

    if not records:
        sys.exit("No topics parsed. Check your syllabus files and --exam filter.")

    print(f"\nTotal topics to ingest: {len(records)}")

    # ---- Dry run ----
    if args.dry_run:
        print("\n=== DRY RUN — no DB writes ===")
        by_exam: dict[str, list[TopicRecord]] = {}
        for r in records:
            by_exam.setdefault(r.exam_name, []).append(r)
        for exam, recs in by_exam.items():
            print(f"\n  {exam}  ({len(recs)} topics)")
            by_subject: dict[str, list[TopicRecord]] = {}
            for r in recs:
                by_subject.setdefault(r.subject, []).append(r)
            for subj, srecs in by_subject.items():
                print(f"    {subj}:")
                for r in srecs:
                    subs = ", ".join(r.subtopics[:3])
                    if len(r.subtopics) > 3:
                        subs += f"… (+{len(r.subtopics)-3})"
                    print(f"      [{r.priority}] {r.topic_name}  diff={r.difficulty}  hrs={r.estimated_hours}")
                    if subs:
                        print(f"             subtopics: {subs}")
        return

    # ---- DB upserts ----
    print("\nConnecting to PostgreSQL…")
    try:
        conn = await _get_conn(args)
    except Exception as e:
        sys.exit(f"DB connection failed: {e}\nCheck postgres_host / postgres_user / postgres_password in .env")

    print("  Connected.")

    # Upsert exams
    exam_ids: dict[str, str] = {}
    for r in records:
        if r.exam_name not in exam_ids:
            eid = await upsert_exam(conn, r.exam_name, r.syllabus_version)
            exam_ids[r.exam_name] = eid
            print(f"  Upserted exam: {r.exam_name}  id={eid[:8]}…")
        r.exam_id = exam_ids[r.exam_name]

    # Upsert topics
    inserted = 0
    for r in records:
        r.topic_id = await upsert_topic(conn, r)
        inserted += 1

    print(f"  Upserted {inserted} topics.")

    # Resolve prerequisites
    await resolve_prerequisites(conn, records)
    print("  Resolved prerequisites.")

    # ---- Embeddings ----
    if args.no_embed:
        print("  Skipping embeddings (--no-embed).")
        await conn.close()
        return

    # Decide which topics need embedding
    if args.reembed:
        to_embed = records
    else:
        # Only embed topics that don't already have a vector
        ids_needing = []
        for r in records:
            if not r.topic_id:
                continue
            has = await conn.fetchval(
                "SELECT embedding_vector IS NOT NULL FROM syllabus_topics WHERE id=$1::uuid",
                r.topic_id,
            )
            if not has:
                ids_needing.append(r)
        to_embed = ids_needing

    if not to_embed:
        print("  All topics already have embeddings. Use --reembed to regenerate.")
    else:
        print(f"\nGenerating embeddings for {len(to_embed)} topic(s)…")

        if args.embedder == "ollama":
            print("  Using Ollama (nomic-embed-text, 768 dims)")
            print("  Make sure your schema uses VECTOR(768)")
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            embedder = OllamaEmbedder(base_url)
        elif args.embedder == "huggingface":
            model_name = os.environ.get("HF_EMBED_MODEL", "BAAI/bge-large-en-v1.5")
            print(f"  Using HuggingFace sentence-transformers: {model_name}")
            embedder = HuggingFaceEmbedder(model_name)
        else:
            api_key = os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                print("  ⚠️  OPENAI_API_KEY not set — skipping embeddings.")
                print("     Run with --no-embed or set OPENAI_API_KEY in .env")
                await conn.close()
                return
            print(f"  Using OpenAI ({OpenAIEmbedder.MODEL}, 1536 dims)")
            embedder = OpenAIEmbedder(api_key)

        texts = [r.embed_text() for r in to_embed]
        t0 = time.time()
        try:
            embeddings = await embedder.embed_batch(texts)
        except Exception as e:
            print(f"  Embedding failed: {e}")
            await conn.close()
            return

        elapsed = time.time() - t0
        print(f"  Embedded {len(embeddings)} topics in {elapsed:.1f}s")

        for r, emb in zip(to_embed, embeddings):
            await update_embedding(conn, r.topic_id, emb)

        print(f"  ✓ Wrote {len(embeddings)} vectors to syllabus_topics.embedding_vector")

    # ---- Rebuild index ----
    if args.rebuild_index:
        await rebuild_ivfflat_index(conn)

    await conn.close()

    # ---- Summary ----
    print("\n========================================")
    print("Ingestion complete.")
    by_exam: dict[str, int] = {}
    for r in records:
        by_exam[r.exam_name] = by_exam.get(r.exam_name, 0) + 1
    for exam, count in by_exam.items():
        print(f"  {exam}: {count} topics")
    print("\nNext steps:")
    print("  1. Run the app:  docker compose up")
    print("  2. Create a user in the users table")
    print("  3. POST /study/onboard  to generate your first study plan")
    print("  4. After bulk insert, run:  python ingest_syllabus.py --rebuild-index")
    print("========================================\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest syllabus files into the AI Study Companion PostgreSQL database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Examples:
          python ingest_syllabus.py --dry-run
          python ingest_syllabus.py
          python ingest_syllabus.py --reembed
          python ingest_syllabus.py --no-embed
          python ingest_syllabus.py --embedder huggingface
          python ingest_syllabus.py --embedder ollama
          python ingest_syllabus.py --exam "SSC CGL"
          python ingest_syllabus.py --rebuild-index
        """),
    )
    parser.add_argument("--data-dir", default="./data",
                        help="Directory containing syllabus .md/.pdf files (default: ./data)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse files and show what would be inserted; no DB writes")
    parser.add_argument("--reembed", action="store_true",
                        help="Re-generate embeddings for all topics, even those already embedded")
    parser.add_argument("--no-embed", action="store_true",
                        help="Skip embedding entirely; only populate topics table")
    parser.add_argument("--embedder", choices=["openai", "ollama", "huggingface"],
                        default="huggingface",
                        help="Embedding model to use (default: huggingface)")
    parser.add_argument("--exam", default=None,
                        help='Only ingest topics for this exam, e.g. "SSC CGL"')
    parser.add_argument("--rebuild-index", action="store_true",
                        help="Rebuild ivfflat vector index after inserts (run after bulk load)")

    args = parser.parse_args()
    asyncio.run(main(args))
