# n8n Plan Reminder Agent

This workflow checks Supabase each day, finds the active study-plan day for the current date, sends a reminder, then records that the reminder was sent.

## Supabase Setup

Run:

```sql
scripts/setup_n8n_reminders.sql
```

It creates:

- `plan_reminders`: stores sent reminder records.
- `get_due_plan_reminders(p_reminder_date, p_channel)`: returns pending plan days that have not already received a reminder for that date and channel.

## n8n Workflow

1. **Schedule Trigger**
   - Run once per day at the learner reminder time.

2. **Date & Time**
   - Timezone: `Asia/Kolkata`
   - Format today as `YYYY-MM-DD`.

3. **HTTP Request: Fetch Due Reminders**
   - Method: `POST`
   - URL: `{{$env.SUPABASE_URL}}/rest/v1/rpc/get_due_plan_reminders`
   - Headers:
     - `apikey: {{$env.SUPABASE_ANON_KEY}}`
     - `Authorization: Bearer {{$env.SUPABASE_ANON_KEY}}`
     - `Content-Type: application/json`
   - Body:

```json
{
  "p_reminder_date": "{{$json.today}}",
  "p_channel": "email"
}
```

4. **Send Reminder**
   - Use Email, WhatsApp, Telegram, or SMS.
   - Example message:

```text
Hi {{$json.user_name}},

Today is Day {{$json.day_number}} of your study plan.

Topic: {{$json.topic_name}}
Subject: {{$json.subject}}
Time: {{$json.allocated_minutes}} minutes

Open your study room and complete today's lesson.
```

5. **HTTP Request: Store Sent Reminder**
   - Method: `POST`
   - URL: `{{$env.SUPABASE_URL}}/rest/v1/plan_reminders`
   - Headers:
     - `apikey: {{$env.SUPABASE_ANON_KEY}}`
     - `Authorization: Bearer {{$env.SUPABASE_ANON_KEY}}`
     - `Content-Type: application/json`
     - `Prefer: resolution=ignore-duplicates`
   - Body:

```json
{
  "user_id": "{{$json.user_id}}",
  "plan_id": "{{$json.plan_id}}",
  "plan_day_id": "{{$json.plan_day_id}}",
  "channel": "email",
  "reminder_date": "{{$json.scheduled_date}}",
  "delivery_meta": {
    "provider": "n8n"
  }
}
```

## Manual Test

Call the RPC with today's date:

```json
{
  "p_reminder_date": "2026-05-03",
  "p_channel": "email"
}
```

If a learner has an active plan day scheduled for that date and `status = 'pending'`, the RPC returns one row for the reminder.

