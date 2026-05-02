-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";    -- for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";      -- pgvector for embedding_vector

-- ============================================================
-- TABLE: exams
-- ============================================================
CREATE TABLE IF NOT EXISTS exams (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             VARCHAR(100) UNIQUE NOT NULL,     -- "SSC CGL", "SBI PO"
    description      TEXT,
    syllabus_version VARCHAR(20) NOT NULL,
    is_active        BOOLEAN DEFAULT true
);

-- ============================================================
-- TABLE: users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name           VARCHAR(120) NOT NULL,
    email          VARCHAR(255) UNIQUE NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT now(),
    level          VARCHAR(20) DEFAULT 'beginner'      -- beginner | intermediate | advanced
                   CHECK (level IN ('beginner','intermediate','advanced')),
    target_exam_id UUID REFERENCES exams(id),
    timezone       VARCHAR(60) DEFAULT 'Asia/Kolkata'
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================================
-- TABLE: syllabus_topics  (RAG seed table - SINGLE SOURCE OF TRUTH)
-- ============================================================
-- CRITICAL: Agents MUST query here. Never let LLM free-generate topic names.
CREATE TABLE IF NOT EXISTS syllabus_topics (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    exam_id          UUID NOT NULL REFERENCES exams(id),
    subject          VARCHAR(60) NOT NULL,              -- "Quantitative Aptitude" | "Logical Reasoning"
    topic_name       VARCHAR(120) NOT NULL,             -- "Percentage", "Time & Work"
    subtopics        TEXT[] NOT NULL DEFAULT '{}',      -- array of subtopic strings
    difficulty       SMALLINT NOT NULL CHECK (difficulty BETWEEN 1 AND 5),
    priority         VARCHAR(10) NOT NULL CHECK (priority IN ('HIGH','MED','LOW')),
    estimated_hours  NUMERIC(4,1) NOT NULL,
    prerequisite_ids UUID[] DEFAULT '{}',               -- soft refs for ordering
    embedding_vector vector(1024),                      -- pgvector - for RAG
    template_ids     UUID[] DEFAULT '{}',               -- -> quiz_templates
    created_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_syllabus_exam_subject ON syllabus_topics(exam_id, subject);
CREATE INDEX IF NOT EXISTS idx_syllabus_embedding
    ON syllabus_topics USING ivfflat (embedding_vector vector_cosine_ops)
    WITH (lists = 100);                                -- rebuild after bulk inserts

-- ============================================================
-- TABLE: study_plans
-- ============================================================
CREATE TABLE IF NOT EXISTS study_plans (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id),
    exam_id          UUID NOT NULL REFERENCES exams(id),
    start_date       DATE NOT NULL,
    end_date         DATE NOT NULL,
    duration_days    SMALLINT GENERATED ALWAYS AS
                     (CAST(end_date - start_date AS SMALLINT)) STORED,
    status           VARCHAR(20) DEFAULT 'active'
                     CHECK (status IN ('active','completed','abandoned')),
    planner_version  SMALLINT DEFAULT 1,
    meta             JSONB DEFAULT '{}',               -- planner reasoning trace (audit only)
    created_at       TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_study_plans_user_status ON study_plans(user_id, status);
-- One active plan per user at a time
CREATE UNIQUE INDEX IF NOT EXISTS uniq_one_active_plan
    ON study_plans(user_id, start_date)
    WHERE status = 'active';

-- ============================================================
-- TABLE: study_plan_days
-- ============================================================
CREATE TABLE IF NOT EXISTS study_plan_days (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id             UUID NOT NULL REFERENCES study_plans(id),
    day_number          SMALLINT NOT NULL CHECK (day_number > 0),
    scheduled_date      DATE NOT NULL,
    topic_id            UUID NOT NULL REFERENCES syllabus_topics(id),
    revision_topic_ids  UUID[] DEFAULT '{}',           -- topics to revise today (day N-2 topic)
    allocated_minutes   SMALLINT NOT NULL DEFAULT 90,
    status              VARCHAR(20) DEFAULT 'pending'
                        CHECK (status IN ('pending','taught','skipped')),
    taught_at           TIMESTAMPTZ                    -- set by Teacher Agent
);
CREATE INDEX IF NOT EXISTS idx_plan_days_plan_date ON study_plan_days(plan_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_plan_days_topic ON study_plan_days(topic_id);

-- ============================================================
-- TABLE: user_performance  (core personalization - update after every quiz)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_performance (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id),
    topic_id         UUID NOT NULL REFERENCES syllabus_topics(id),
    attempts         INTEGER DEFAULT 0,
    correct          INTEGER DEFAULT 0,
    accuracy         NUMERIC(5,2) GENERATED ALWAYS AS
                     (correct * 100.0 / NULLIF(attempts, 0)) STORED,
    avg_time_secs    NUMERIC(6,2) DEFAULT 0,
    last_attempted   TIMESTAMPTZ DEFAULT now(),
    weakness_score   NUMERIC(5,2) DEFAULT 50,          -- 0=strong, 100=very weak
    -- Formula (applied in Progress Analyzer tool, stored here):
    -- weakness_score = (1 - accuracy/100) * 70 + recency_weight * 30
    -- recency_weight = max(0, 1 - days_since_last_attempt / 14)
    UNIQUE (user_id, topic_id)
);
CREATE INDEX IF NOT EXISTS idx_perf_user_weakness
    ON user_performance(user_id, weakness_score DESC);

-- ============================================================
-- TABLE: quiz_templates  (MANDATORY for Puzzles, Series, Direction Sense)
-- ============================================================
CREATE TABLE IF NOT EXISTS quiz_templates (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id       UUID NOT NULL REFERENCES syllabus_topics(id),
    template_type  VARCHAR(40) NOT NULL
                   CHECK (template_type IN ('mcq','fill','match','arrange','puzzle_grid')),
    difficulty     SMALLINT CHECK (difficulty BETWEEN 1 AND 5),
    template_body  JSONB NOT NULL,                     -- {slots, rules, distractors}
    answer_key     JSONB NOT NULL,                     -- correct answer derivation logic
    usage_count    INTEGER DEFAULT 0,
    is_active      BOOLEAN DEFAULT true
);

-- ============================================================
-- TABLE: quiz_attempts
-- ============================================================
CREATE TABLE IF NOT EXISTS quiz_attempts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id),
    topic_id         UUID NOT NULL REFERENCES syllabus_topics(id),
    plan_day_id      UUID REFERENCES study_plan_days(id),  -- NULL = standalone quiz
    template_id      UUID REFERENCES quiz_templates(id),
    questions        JSONB NOT NULL,                   -- [{q, options[4], correct_idx, explanation}]
    user_answers     JSONB NOT NULL DEFAULT '[]',      -- [int] chosen indices
    score            SMALLINT,
    total_questions  SMALLINT NOT NULL,
    time_taken_secs  INTEGER,
    attempted_at     TIMESTAMPTZ DEFAULT now(),
    submitted_at     TIMESTAMPTZ                       -- NULL = incomplete/timed out
);
CREATE INDEX IF NOT EXISTS idx_quiz_user_topic_time
    ON quiz_attempts(user_id, topic_id, attempted_at DESC);

-- ============================================================
-- TABLE: weak_areas  (denormalized cache - refreshed by Progress Analyzer)
-- ============================================================
-- Do NOT query user_performance aggregates in real-time for planning.
-- Always read from this table. Refresh via recompute_weakness_score tool.
CREATE TABLE IF NOT EXISTS weak_areas (
    user_id                UUID NOT NULL REFERENCES users(id),
    topic_id               UUID NOT NULL REFERENCES syllabus_topics(id),
    weakness_score         NUMERIC(5,2),
    rank                   SMALLINT,                  -- 1 = weakest overall
    recommended_extra_mins SMALLINT,
    updated_at             TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (user_id, topic_id)
);

-- ============================================================
-- TABLE: teaching_logs
-- ============================================================
CREATE TABLE IF NOT EXISTS teaching_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_day_id      UUID NOT NULL REFERENCES study_plan_days(id),
    user_id          UUID NOT NULL REFERENCES users(id),
    topic_id         UUID NOT NULL REFERENCES syllabus_topics(id),
    content_summary  TEXT,                             -- LLM-generated summary of what was taught
    revision_covered UUID[] DEFAULT '{}',              -- topic IDs revised in this session
    llm_trace        JSONB DEFAULT '{}',               -- ReAct thought/action/observation (debug only)
    duration_mins    SMALLINT,
    taught_at        TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_teaching_user_topic ON teaching_logs(user_id, topic_id);
