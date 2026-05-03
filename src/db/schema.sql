create table if not exists exams (
    id text primary key,
    name text unique not null,
    description text,
    syllabus_version text not null default '2026',
    is_active boolean not null default true,
    source_type text not null default 'manual',
    source_document_id text,
    created_at timestamptz not null default now()
);

create table if not exists users (
    id text primary key,
    name text not null,
    email text unique not null,
    level text not null default 'beginner' check (level in ('beginner', 'intermediate', 'advanced')),
    target_exam_id text references exams(id),
    timezone text not null default 'Asia/Kolkata',
    created_at timestamptz not null default now()
);

create table if not exists syllabus_topics (
    id text primary key,
    exam_id text not null references exams(id),
    subject text not null,
    topic_name text not null,
    subtopics jsonb not null default '[]',
    difficulty smallint not null check (difficulty between 1 and 5),
    priority text not null check (priority in ('HIGH', 'MED', 'LOW')),
    estimated_hours numeric(4,1) not null default 0,
    prerequisite_ids jsonb not null default '[]',
    template_ids jsonb not null default '[]',
    source_document_id text,
    source_query text,
    created_at timestamptz not null default now()
);

create index if not exists idx_syllabus_exam_subject on syllabus_topics(exam_id, subject);

create table if not exists topic_lesson_material (
    id text primary key,
    topic_id text not null references syllabus_topics(id) on delete cascade,
    simple_explanation text not null,
    concept_points jsonb not null default '[]',
    worked_example text not null,
    common_mistakes jsonb not null default '[]',
    quick_trick text not null,
    practice_prompt text not null,
    recap text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_lesson_material_topic on topic_lesson_material(topic_id, is_active);
create index if not exists idx_users_target_exam on users(target_exam_id);

create table if not exists study_plans (
    id text primary key,
    user_id text not null references users(id),
    exam_id text not null references exams(id),
    level text not null default 'beginner',
    start_date date not null,
    end_date date not null,
    duration_days smallint not null,
    status text not null default 'active' check (status in ('active', 'completed', 'abandoned')),
    planner_version smallint not null default 1,
    meta jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_study_plans_user_status on study_plans(user_id, status);
create index if not exists idx_study_plans_exam on study_plans(exam_id);

create table if not exists study_plan_days (
    id text primary key,
    plan_id text not null references study_plans(id) on delete cascade,
    day_number smallint not null check (day_number > 0),
    scheduled_date date not null,
    topic_id text not null references syllabus_topics(id),
    revision_topic_ids jsonb not null default '[]',
    allocated_minutes smallint not null default 90,
    status text not null default 'pending' check (status in ('pending', 'taught', 'skipped')),
    taught_at timestamptz
);

create index if not exists idx_plan_days_plan_date on study_plan_days(plan_id, scheduled_date);
create index if not exists idx_plan_days_topic on study_plan_days(topic_id);

create extension if not exists pgcrypto;

create table if not exists plan_reminders (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references users(id) on delete cascade,
    plan_id text not null references study_plans(id) on delete cascade,
    plan_day_id text not null references study_plan_days(id) on delete cascade,
    channel text not null default 'email',
    reminder_date date not null,
    sent_at timestamptz not null default now(),
    delivery_meta jsonb not null default '{}',
    unique (user_id, plan_day_id, channel, reminder_date)
);

create index if not exists idx_plan_reminders_user_date on plan_reminders(user_id, reminder_date desc);
create index if not exists idx_plan_reminders_day_channel on plan_reminders(plan_day_id, channel);
create index if not exists idx_plan_reminders_plan_id on plan_reminders(plan_id);

create or replace function get_due_plan_reminders(
    p_reminder_date date default current_date,
    p_channel text default 'email'
)
returns table (
    user_id text,
    user_name text,
    user_email text,
    user_timezone text,
    plan_id text,
    plan_day_id text,
    day_number smallint,
    scheduled_date date,
    topic_id text,
    topic_name text,
    subject text,
    allocated_minutes smallint,
    plan_start_date date,
    plan_end_date date
)
language sql stable
set search_path = public
as $$
    select
        users.id as user_id,
        users.name as user_name,
        users.email as user_email,
        users.timezone as user_timezone,
        study_plans.id as plan_id,
        study_plan_days.id as plan_day_id,
        study_plan_days.day_number,
        study_plan_days.scheduled_date,
        study_plan_days.topic_id,
        syllabus_topics.topic_name,
        syllabus_topics.subject,
        study_plan_days.allocated_minutes,
        study_plans.start_date as plan_start_date,
        study_plans.end_date as plan_end_date
    from study_plans
    join users on users.id = study_plans.user_id
    join study_plan_days on study_plan_days.plan_id = study_plans.id
    join syllabus_topics on syllabus_topics.id = study_plan_days.topic_id
    left join plan_reminders
        on plan_reminders.user_id = users.id
        and plan_reminders.plan_day_id = study_plan_days.id
        and plan_reminders.channel = p_channel
        and plan_reminders.reminder_date = p_reminder_date
    where study_plans.status = 'active'
        and study_plan_days.status = 'pending'
        and study_plan_days.scheduled_date = p_reminder_date
        and plan_reminders.id is null
    order by users.id, study_plan_days.day_number;
$$;

create table if not exists quiz_templates (
    id text primary key,
    topic_id text not null references syllabus_topics(id),
    template_type text not null default 'mcq',
    difficulty smallint check (difficulty between 1 and 5),
    template_body jsonb not null default '{}',
    answer_key jsonb not null default '{}',
    usage_count integer not null default 0,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

create index if not exists idx_quiz_templates_topic on quiz_templates(topic_id);

create table if not exists quiz_attempts (
    id text primary key,
    user_id text not null references users(id),
    topic_id text not null references syllabus_topics(id),
    plan_day_id text references study_plan_days(id),
    template_id text references quiz_templates(id),
    questions jsonb not null,
    user_answers jsonb not null default '[]',
    score smallint,
    total_questions smallint not null,
    difficulty smallint,
    adaptive_context jsonb not null default '{}',
    accuracy numeric(5,2),
    time_taken_secs integer,
    attempted_at timestamptz not null default now(),
    submitted_at timestamptz
);

create index if not exists idx_quiz_user_topic_time on quiz_attempts(user_id, topic_id, attempted_at desc);
create index if not exists idx_quiz_attempts_topic on quiz_attempts(topic_id);
create index if not exists idx_quiz_attempts_plan_day on quiz_attempts(plan_day_id);
create index if not exists idx_quiz_attempts_template on quiz_attempts(template_id);

create table if not exists user_performance (
    id text primary key,
    user_id text not null references users(id),
    topic_id text not null references syllabus_topics(id),
    attempts integer not null default 0,
    correct integer not null default 0,
    accuracy numeric(5,2) not null default 0,
    avg_time_secs numeric(6,2) not null default 0,
    last_attempted timestamptz not null default now(),
    weakness_score numeric(5,2) not null default 50,
    unique (user_id, topic_id)
);

create index if not exists idx_perf_user_weakness on user_performance(user_id, weakness_score desc);
create index if not exists idx_user_performance_topic on user_performance(topic_id);

create table if not exists teaching_logs (
    id text primary key,
    plan_day_id text not null references study_plan_days(id),
    user_id text not null references users(id),
    topic_id text not null references syllabus_topics(id),
    content_summary text,
    revision_covered jsonb not null default '[]',
    llm_trace jsonb not null default '{}',
    duration_mins smallint,
    taught_at timestamptz not null default now()
);

create index if not exists idx_teaching_user_topic on teaching_logs(user_id, topic_id);
create index if not exists idx_teaching_logs_plan_day on teaching_logs(plan_day_id);
create index if not exists idx_teaching_logs_topic on teaching_logs(topic_id);

create extension if not exists vector;

create table if not exists rag_documents (
    id text primary key,
    filename text not null,
    storage_path text,
    created_at timestamptz not null default now()
);

create table if not exists rag_chunks (
    id text primary key,
    document_id text not null references rag_documents(id) on delete cascade,
    chunk_index integer not null,
    content text not null,
    metadata jsonb not null default '{}',
    embedding vector(384),
    created_at timestamptz not null default now()
);

create index if not exists idx_rag_chunks_document on rag_chunks(document_id, chunk_index);
create index if not exists idx_rag_chunks_embedding
    on rag_chunks using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create or replace function match_rag_chunks(
    query_embedding vector(384),
    match_count integer default 5
)
returns table (
    id text,
    document_id text,
    content text,
    metadata jsonb,
    similarity double precision
)
language sql stable
set search_path = public, extensions
as $$
    select
        rag_chunks.id,
        rag_chunks.document_id,
        rag_chunks.content,
        rag_chunks.metadata,
        1 - (rag_chunks.embedding <=> query_embedding) as similarity
    from rag_chunks
    where rag_chunks.embedding is not null
    order by rag_chunks.embedding <=> query_embedding
    limit match_count;
$$;

alter table exams enable row level security;
alter table users enable row level security;
alter table syllabus_topics enable row level security;
alter table topic_lesson_material enable row level security;
alter table study_plans enable row level security;
alter table study_plan_days enable row level security;
alter table plan_reminders enable row level security;
alter table quiz_templates enable row level security;
alter table quiz_attempts enable row level security;
alter table user_performance enable row level security;
alter table teaching_logs enable row level security;
alter table rag_documents enable row level security;
alter table rag_chunks enable row level security;

create policy exams_app_all on exams for all to anon, authenticated using (true) with check (true);
create policy users_app_all on users for all to anon, authenticated using (true) with check (true);
create policy syllabus_topics_app_all on syllabus_topics for all to anon, authenticated using (true) with check (true);
create policy topic_lesson_material_app_all on topic_lesson_material for all to anon, authenticated using (true) with check (true);
create policy study_plans_app_all on study_plans for all to anon, authenticated using (true) with check (true);
create policy study_plan_days_app_all on study_plan_days for all to anon, authenticated using (true) with check (true);
create policy plan_reminders_app_all on plan_reminders for all to anon, authenticated using (true) with check (true);
create policy quiz_templates_app_all on quiz_templates for all to anon, authenticated using (true) with check (true);
create policy quiz_attempts_app_all on quiz_attempts for all to anon, authenticated using (true) with check (true);
create policy user_performance_app_all on user_performance for all to anon, authenticated using (true) with check (true);
create policy teaching_logs_app_all on teaching_logs for all to anon, authenticated using (true) with check (true);
create policy rag_documents_app_all on rag_documents for all to anon, authenticated using (true) with check (true);
create policy rag_chunks_app_all on rag_chunks for all to anon, authenticated using (true) with check (true);
