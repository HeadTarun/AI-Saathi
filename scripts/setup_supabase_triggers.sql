-- Supabase trigger setup for the study/RAG schema.
--
-- Safe to run more than once. This script does not generate embeddings; the app
-- creates embeddings in Python with BAAI/bge-small-en-v1.5 and stores them here.

create extension if not exists vector;

alter table exams add column if not exists updated_at timestamptz not null default now();
alter table exams add column if not exists source_type text not null default 'manual';
alter table exams add column if not exists source_document_id text;
alter table users add column if not exists updated_at timestamptz not null default now();
alter table syllabus_topics add column if not exists updated_at timestamptz not null default now();
alter table syllabus_topics add column if not exists source_document_id text;
alter table syllabus_topics add column if not exists source_query text;
alter table topic_lesson_material add column if not exists updated_at timestamptz not null default now();
alter table study_plans add column if not exists updated_at timestamptz not null default now();
alter table study_plan_days add column if not exists updated_at timestamptz not null default now();
alter table quiz_templates add column if not exists updated_at timestamptz not null default now();
alter table quiz_attempts add column if not exists updated_at timestamptz not null default now();
alter table quiz_attempts add column if not exists adaptive_context jsonb not null default '{}';
alter table user_performance add column if not exists updated_at timestamptz not null default now();
alter table teaching_logs add column if not exists updated_at timestamptz not null default now();
alter table rag_documents add column if not exists updated_at timestamptz not null default now();
alter table rag_chunks add column if not exists updated_at timestamptz not null default now();

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public, extensions
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists trg_exams_updated_at on exams;
create trigger trg_exams_updated_at
before update on exams
for each row execute function public.set_updated_at();

drop trigger if exists trg_users_updated_at on users;
create trigger trg_users_updated_at
before update on users
for each row execute function public.set_updated_at();

drop trigger if exists trg_syllabus_topics_updated_at on syllabus_topics;
create trigger trg_syllabus_topics_updated_at
before update on syllabus_topics
for each row execute function public.set_updated_at();

drop trigger if exists trg_topic_lesson_material_updated_at on topic_lesson_material;
create trigger trg_topic_lesson_material_updated_at
before update on topic_lesson_material
for each row execute function public.set_updated_at();

drop trigger if exists trg_study_plans_updated_at on study_plans;
create trigger trg_study_plans_updated_at
before update on study_plans
for each row execute function public.set_updated_at();

drop trigger if exists trg_study_plan_days_updated_at on study_plan_days;
create trigger trg_study_plan_days_updated_at
before update on study_plan_days
for each row execute function public.set_updated_at();

drop trigger if exists trg_quiz_templates_updated_at on quiz_templates;
create trigger trg_quiz_templates_updated_at
before update on quiz_templates
for each row execute function public.set_updated_at();

drop trigger if exists trg_quiz_attempts_updated_at on quiz_attempts;
create trigger trg_quiz_attempts_updated_at
before update on quiz_attempts
for each row execute function public.set_updated_at();

drop trigger if exists trg_user_performance_updated_at on user_performance;
create trigger trg_user_performance_updated_at
before update on user_performance
for each row execute function public.set_updated_at();

drop trigger if exists trg_teaching_logs_updated_at on teaching_logs;
create trigger trg_teaching_logs_updated_at
before update on teaching_logs
for each row execute function public.set_updated_at();

drop trigger if exists trg_rag_documents_updated_at on rag_documents;
create trigger trg_rag_documents_updated_at
before update on rag_documents
for each row execute function public.set_updated_at();

drop trigger if exists trg_rag_chunks_updated_at on rag_chunks;
create trigger trg_rag_chunks_updated_at
before update on rag_chunks
for each row execute function public.set_updated_at();

-- Repair the RAG document relationship in older Supabase databases.
delete from rag_chunks
where document_id is null
   or not exists (
       select 1
       from rag_documents
       where rag_documents.id = rag_chunks.document_id
   );

alter table rag_chunks
    alter column document_id set not null;

alter table rag_chunks
    drop constraint if exists rag_chunks_document_id_fkey;

alter table rag_chunks
    add constraint rag_chunks_document_id_fkey
    foreign key (document_id)
    references rag_documents(id)
    on delete cascade;

create or replace function public.validate_rag_chunk_embedding()
returns trigger
language plpgsql
set search_path = public, extensions
as $$
begin
    if new.embedding is not null and vector_dims(new.embedding) <> 384 then
        raise exception 'rag_chunks.embedding must be 384 dimensions, got %', vector_dims(new.embedding);
    end if;

    return new;
end;
$$;

drop trigger if exists trg_validate_rag_chunk_embedding on rag_chunks;
create trigger trg_validate_rag_chunk_embedding
before insert or update of embedding on rag_chunks
for each row execute function public.validate_rag_chunk_embedding();

create or replace function public.touch_rag_document_from_chunk()
returns trigger
language plpgsql
set search_path = public, extensions
as $$
declare
    target_document_id text;
begin
    if tg_op = 'DELETE' then
        target_document_id = old.document_id;
    else
        target_document_id = new.document_id;
    end if;

    update rag_documents
    set updated_at = now()
    where id = target_document_id;

    return null;
end;
$$;

drop trigger if exists trg_touch_rag_document_insert on rag_chunks;
create trigger trg_touch_rag_document_insert
after insert on rag_chunks
for each row execute function public.touch_rag_document_from_chunk();

drop trigger if exists trg_touch_rag_document_update on rag_chunks;
create trigger trg_touch_rag_document_update
after update on rag_chunks
for each row execute function public.touch_rag_document_from_chunk();

drop trigger if exists trg_touch_rag_document_delete on rag_chunks;
create trigger trg_touch_rag_document_delete
after delete on rag_chunks
for each row execute function public.touch_rag_document_from_chunk();

create index if not exists idx_users_target_exam on users(target_exam_id);
create index if not exists idx_study_plans_exam on study_plans(exam_id);
create index if not exists idx_quiz_templates_topic on quiz_templates(topic_id);
create index if not exists idx_quiz_attempts_topic on quiz_attempts(topic_id);
create index if not exists idx_quiz_attempts_plan_day on quiz_attempts(plan_day_id);
create index if not exists idx_quiz_attempts_template on quiz_attempts(template_id);
create index if not exists idx_user_performance_topic on user_performance(topic_id);
create index if not exists idx_teaching_logs_plan_day on teaching_logs(plan_day_id);
create index if not exists idx_teaching_logs_topic on teaching_logs(topic_id);

drop index if exists rag_chunks_embedding_idx;

alter table exams enable row level security;
alter table users enable row level security;
alter table syllabus_topics enable row level security;
alter table topic_lesson_material enable row level security;
alter table study_plans enable row level security;
alter table study_plan_days enable row level security;
alter table quiz_templates enable row level security;
alter table quiz_attempts enable row level security;
alter table user_performance enable row level security;
alter table teaching_logs enable row level security;
alter table rag_documents enable row level security;
alter table rag_chunks enable row level security;

drop policy if exists exams_app_all on exams;
drop policy if exists users_app_all on users;
drop policy if exists syllabus_topics_app_all on syllabus_topics;
drop policy if exists topic_lesson_material_app_all on topic_lesson_material;
drop policy if exists study_plans_app_all on study_plans;
drop policy if exists study_plan_days_app_all on study_plan_days;
drop policy if exists quiz_templates_app_all on quiz_templates;
drop policy if exists quiz_attempts_app_all on quiz_attempts;
drop policy if exists user_performance_app_all on user_performance;
drop policy if exists teaching_logs_app_all on teaching_logs;
drop policy if exists rag_documents_app_all on rag_documents;
drop policy if exists rag_chunks_app_all on rag_chunks;

create policy exams_app_all on exams for all to anon, authenticated using (true) with check (true);
create policy users_app_all on users for all to anon, authenticated using (true) with check (true);
create policy syllabus_topics_app_all on syllabus_topics for all to anon, authenticated using (true) with check (true);
create policy topic_lesson_material_app_all on topic_lesson_material for all to anon, authenticated using (true) with check (true);
create policy study_plans_app_all on study_plans for all to anon, authenticated using (true) with check (true);
create policy study_plan_days_app_all on study_plan_days for all to anon, authenticated using (true) with check (true);
create policy quiz_templates_app_all on quiz_templates for all to anon, authenticated using (true) with check (true);
create policy quiz_attempts_app_all on quiz_attempts for all to anon, authenticated using (true) with check (true);
create policy user_performance_app_all on user_performance for all to anon, authenticated using (true) with check (true);
create policy teaching_logs_app_all on teaching_logs for all to anon, authenticated using (true) with check (true);
create policy rag_documents_app_all on rag_documents for all to anon, authenticated using (true) with check (true);
create policy rag_chunks_app_all on rag_chunks for all to anon, authenticated using (true) with check (true);

revoke execute on function public.rls_auto_enable() from public;
revoke execute on function public.rls_auto_enable() from anon;
revoke execute on function public.rls_auto_enable() from authenticated;
