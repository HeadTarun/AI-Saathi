-- Supabase setup for the n8n daily study-plan reminder agent.
-- Run this in the Supabase SQL editor, or through a Postgres connection.

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

create index if not exists idx_plan_reminders_user_date
    on plan_reminders(user_id, reminder_date desc);

create index if not exists idx_plan_reminders_day_channel
    on plan_reminders(plan_day_id, channel);

create index if not exists idx_plan_reminders_plan_id
    on plan_reminders(plan_id);

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

grant execute on function get_due_plan_reminders(date, text) to anon, authenticated;

alter table plan_reminders enable row level security;

drop policy if exists plan_reminders_app_all on plan_reminders;
create policy plan_reminders_app_all
    on plan_reminders
    for all
    to anon, authenticated
    using (true)
    with check (true);
