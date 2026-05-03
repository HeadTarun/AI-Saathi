# AI-SAATHI PPT Content

## Slide 1: Title

### AI-SAATHI

An AI-powered, adaptive study companion for exam preparation.

**Tagline:** Plan smarter. Learn actively. Improve continuously.

**Presented by:** Team AI-SAATHI

---

## Slide 2: The Problem

Students preparing for aptitude, reasoning, and competitive exams often struggle with:

- No clear short-term study roadmap.
- Difficulty knowing which topic to study first.
- Passive learning without enough practice.
- Lack of personalized feedback after quizzes.
- Weak topics remaining hidden until exam time.
- Low motivation because progress is not visible.
- No automatic revision or replanning when performance drops.

**Core problem:** Most learners do not need only content. They need a guided system that plans, teaches, tests, tracks, and adapts.

---

## Slide 3: Why This Problem Matters

Exam preparation is time-sensitive. Students often have only a few days or weeks to prepare, but they waste time deciding what to study, searching for material, and repeating topics randomly.

Without a smart feedback loop:

- Strong topics get repeated unnecessarily.
- Weak topics are ignored.
- Study plans become outdated after one bad quiz.
- Learners lose confidence and consistency.

AI-SAATHI solves this by converting preparation into a structured daily learning journey.

---

## Slide 4: Proposed Solution

AI-SAATHI is a gamified AI study companion that creates a personalized study plan, teaches each topic step-by-step, generates quizzes, tracks performance, and adjusts the remaining plan based on weak areas.

The system supports:

- User onboarding and study goal selection.
- 2 to 7 day personalized study plans.
- Daily study room with guided lessons.
- Adaptive quiz generation.
- Quiz scoring and instant feedback.
- Weakness tracking.
- Progress dashboard with XP, badges, streaks, and activity heatmap.
- Replanning when quiz performance is below the pass mark.
- Reminder workflow through Supabase and n8n.

---

## Slide 5: Project Vision

AI-SAATHI aims to become a personal AI study partner for students who want focused, measurable, and motivating exam preparation.

Instead of giving generic notes, it behaves like a learning coach:

- It understands the learner's exam goal.
- It builds a realistic plan.
- It teaches one concept at a time.
- It checks understanding through quizzes.
- It remembers performance.
- It adapts the next steps.

---

## Slide 6: Target Users

AI-SAATHI is designed for:

- Students preparing for aptitude and reasoning tests.
- Placement preparation learners.
- Competitive exam aspirants.
- Beginners who need guided topic sequencing.
- Learners who want short, focused study plans.
- Users who benefit from gamified motivation.

Initial focus area:

- Aptitude and reasoning foundation topics such as Percentage, Profit & Loss, Ratio & Proportion, Time & Work, Time-Speed-Distance, Number Series, Coding-Decoding, Blood Relations, Direction Sense, and Syllogism.

---

## Slide 7: Unique Selling Proposition

### USP: A closed-loop AI learning system

AI-SAATHI is not just a chatbot, quiz app, or static learning platform. It combines planning, teaching, testing, performance analysis, and replanning into one loop.

Key USPs:

- **Adaptive study plans:** Plans are created based on exam, level, goal, duration, priority, difficulty, and weak areas.
- **AI teaching flow:** Lessons include Socratic hooks, concept explanation, real-world examples, shortcuts, guided practice, and recap.
- **RAG-powered learning material:** Uses Supabase vector search and fallback knowledge sources for grounded lessons.
- **Performance-based quiz adaptation:** Quiz difficulty adapts using saved accuracy and attempts.
- **Automatic weakness tracking:** Every quiz updates accuracy, attempts, average time, and weakness score.
- **Replanning engine:** Low scores trigger plan adjustment for remaining days.
- **Gamification:** XP, levels, badges, streaks, and heatmaps make progress visible.
- **Reminder automation:** n8n workflow can remind learners about the current day's study task.

---

## Slide 8: Core Features

- **Authentication:** Email/password and Google login support in frontend flow.
- **Study plan generation:** Learner selects exam, level, goal, and duration.
- **Dashboard:** Shows active plan, daily roadmap, progress percentage, and locked/unlocked days.
- **Study room:** Opens the current lesson and guides the learner step-by-step.
- **Quiz battle:** Generates multiple-choice questions for the current topic.
- **Instant result:** Shows score, accuracy, pass/fail status, and recommended action.
- **Profile page:** Shows XP, badges, streaks, heatmap, topic performance, and weak areas.
- **Adjust plan:** Allows replanning based on saved performance.
- **Reminder agent:** Sends daily study reminders through an n8n workflow.

---

## Slide 9: User Journey

1. User signs up or logs in.
2. User chooses exam goal, level, duration, and personal target.
3. AI-SAATHI creates a short study plan.
4. User opens the dashboard and selects an unlocked day.
5. Study room teaches the topic with personalized lesson steps.
6. User takes a quiz battle.
7. System scores the quiz and stores the attempt.
8. Performance table updates accuracy and weakness score.
9. If the learner passes, the next day unlocks.
10. If the learner scores below the pass mark, replanning is triggered.
11. Profile dashboard shows growth through XP, badges, streaks, and topic stats.

---

## Slide 10: Business Logic Overview

AI-SAATHI uses a learning feedback loop:

**Plan -> Teach -> Quiz -> Evaluate -> Track -> Replan -> Continue**

Business logic rules:

- A learner can create a study plan for 2 to 7 days.
- Topics are selected using priority, difficulty, prerequisites, and weak areas.
- Each plan day has one main topic and optional revision topics.
- A lesson is marked as taught when the study room opens successfully.
- Quiz attempts are stored before submission.
- Pass mark is 65%.
- If accuracy is 65% or above, the learner can continue.
- If accuracy is below 65%, the system recommends revision and flags replanning.
- Weakness score increases when accuracy is low.
- Pending plan days can be reordered according to weak topics.

---

## Slide 11: Study Plan Logic

The planner creates a structured daily roadmap using:

- User ID and profile.
- Target exam.
- Study duration.
- Current level.
- User goal.
- Topic priority.
- Topic difficulty.
- Estimated study hours.
- Existing weak-area performance.

The output is a daily plan containing:

- Day number.
- Scheduled date.
- Topic ID.
- Topic name.
- Subject.
- Difficulty.
- Priority.
- Allocated minutes.
- Revision topic IDs.
- Lock/unlock status.

---

## Slide 12: Teaching Logic

The teaching module creates a lesson for the selected plan day.

It uses:

- Current plan day.
- Topic details.
- Lesson material from Supabase.
- RAG chunks when available.
- External aptitude/reasoning fallback knowledge.
- Previous topic revision.
- Learner performance data.

Lesson structure:

- Think first.
- Connect yesterday.
- Build the idea.
- Real-world example.
- Exam trick.
- Guided practice.
- Recap.

This makes the lesson active instead of passive.

---

## Slide 13: Quiz Logic

The quiz module generates multiple-choice questions for the current topic.

Quiz generation uses:

- Topic ID.
- Number of questions.
- Requested difficulty.
- Adaptive difficulty from user performance.
- Saved quiz templates.
- Knowledge-based fallback templates if templates are missing.

Quiz submission calculates:

- Score.
- Total questions.
- Accuracy.
- Per-question correctness.
- Updated user accuracy.
- New weakness score.
- Pass/fail status.
- Whether replanning is triggered.
- Recommended next action.

---

## Slide 14: Progress And Gamification Logic

AI-SAATHI stores every quiz attempt and converts performance into visible progress.

Progress metrics:

- Topic-wise attempts.
- Correct answers.
- Accuracy percentage.
- Weakness score.
- Average time per question.
- Top weak topics.

Gamification metrics:

- XP points.
- Level.
- Level progress.
- Current streak.
- Best streak.
- Monthly activity heatmap.
- Badges for milestones such as first quiz, 70% accuracy, 3-day streak, 100 questions, topic clear, and steady learning.

This motivates the learner to return and complete the plan.

---

## Slide 15: Replanning Logic

Replanning happens when performance shows that the current plan is no longer ideal.

Trigger:

- Quiz accuracy below 65%.

Replanning steps:

1. Fetch active study plan.
2. Fetch weak-area scores.
3. Identify pending days.
4. Sort pending topics by weakness score.
5. Allocate more time to high-weakness topics.
6. Add revision links from previous topics.
7. Update plan metadata.
8. Clear the replan flag.

Result:

- The learner's remaining plan becomes more focused on weak topics.

---

## Slide 16: System Architecture

### Frontend

- Next.js app.
- Pages for landing, signup, login, plan generation, dashboard, study room, and profile.
- API client connects to backend study endpoints.
- Supabase auth integration.
- Gamified UI with study roadmap, quiz battle, XP, streaks, and badges.

### Backend

- FastAPI service.
- Study API routes under `/study`.
- Local multi-agent router.
- Planner agent, teacher agent, quiz agent, and progress agent.
- Core business logic in `study_core.py`.

### Database And Storage

- Supabase Postgres.
- Tables for users, exams, syllabus topics, study plans, plan days, lesson material, quiz templates, quiz attempts, performance, teaching logs, reminders, RAG documents, and RAG chunks.
- pgvector for RAG similarity search.

### Automation

- n8n reminder workflow.
- Supabase RPC for due reminders.

---

## Slide 17: Multi-Agent Design

AI-SAATHI uses a router-agent pattern.

Agents:

- **Study Router:** Routes tasks to the correct specialized agent.
- **Planner Agent:** Builds plans, fetches plans, lists exams, and replans.
- **Teacher Agent:** Teaches a plan day and creates lesson content.
- **Quiz Agent:** Generates quizzes and submits quiz answers.
- **Progress Agent:** Returns topic stats, weak areas, and activity data.

Why this matters:

- Each agent has a clear responsibility.
- The system is easier to extend.
- Future agents can be added for doubt solving, voice teaching, mentor review, or job-specific preparation.

---

## Slide 18: Database Model

Important tables:

- `users`: learner profile and target exam.
- `exams`: exam definitions.
- `syllabus_topics`: topic list, priority, difficulty, subtopics, estimated hours.
- `study_plans`: active plan metadata.
- `study_plan_days`: day-wise topics and schedule.
- `topic_lesson_material`: reusable lesson content.
- `quiz_templates`: question templates.
- `quiz_attempts`: saved quiz sessions and answers.
- `user_performance`: accuracy, attempts, weakness score.
- `teaching_logs`: lesson history.
- `rag_documents` and `rag_chunks`: document-based learning material.
- `plan_reminders`: reminder delivery records.

---

## Slide 19: APIs Used In The Project

Main backend endpoints:

- `GET /study/exams`: List study goals.
- `POST /study/onboard`: Create learner plan.
- `GET /study/plan/{user_id}`: Fetch active plan.
- `POST /study/teach/{plan_day_id}`: Generate lesson for a day.
- `GET /study/teach/{plan_day_id}/stream`: Stream lesson preparation status.
- `POST /study/quiz/generate`: Generate quiz.
- `POST /study/quiz/{attempt_id}/submit`: Submit quiz and update performance.
- `GET /study/progress/{user_id}`: Fetch progress data.
- `POST /study/replan/{user_id}`: Adjust pending plan days.
- `GET /study/profile/{user_id}`: Fetch profile, active plan, and progress.

---

## Slide 20: Technology Stack

### Frontend

- Next.js
- TypeScript
- CSS
- Supabase client

### Backend

- Python
- FastAPI
- Pydantic
- LangChain tool wrappers

### Database

- Supabase Postgres
- pgvector
- SQL functions and triggers

### AI And Retrieval

- Sentence Transformers embedding model.
- Supabase vector similarity search.
- RAG content retrieval.
- External aptitude/reasoning knowledge fallback.

### Automation

- n8n for daily reminders.

---

## Slide 21: Business Model Possibilities

AI-SAATHI can be positioned as an EdTech SaaS product.

Possible revenue models:

- Freemium plan with limited study plans and quizzes.
- Premium subscription for unlimited adaptive plans, analytics, and reminders.
- Institution dashboard for colleges and coaching centers.
- Placement preparation package for universities.
- Corporate training version for employee skill assessment.
- Paid topic packs for exams, interviews, and certification preparation.

Potential customers:

- Students.
- Colleges.
- Coaching institutes.
- Placement cells.
- Training companies.

---

## Slide 22: Market Advantage

AI-SAATHI stands out because it does not stop at content delivery.

Competitive advantages:

- Personalized micro-plans instead of generic courses.
- Learning and assessment in the same flow.
- Data-backed weakness detection.
- Automatic replanning after low performance.
- Gamified progress for motivation.
- RAG-ready architecture for adding new documents and exams.
- Modular agent architecture for future expansion.

---

## Slide 23: Impact

For learners:

- Less confusion about what to study.
- Better revision discipline.
- More active learning.
- Clear feedback after every quiz.
- Higher motivation through visible progress.

For institutions:

- Track learner progress.
- Identify weak areas at scale.
- Offer structured preparation programs.
- Reduce manual mentoring load.

For business:

- Scalable exam-prep platform.
- Easy to expand across exams and courses.
- Strong retention through daily plans, reminders, and gamification.

---

## Slide 24: Implementation Challenges

Challenges faced or expected:

- Designing a planner that creates useful study plans within only 2 to 7 days.
- Balancing topic priority, difficulty, and weakness score.
- Creating fallback lessons when RAG content is missing.
- Keeping quiz questions relevant and not repetitive.
- Updating performance accurately after each attempt.
- Avoiding overcomplicated agent logic while keeping the system modular.
- Handling locked and unlocked study days correctly.
- Maintaining frontend and backend state consistency.
- Integrating Supabase authentication, database, vector search, and API flows.
- Supporting reminders without sending duplicate notifications.

---

## Slide 25: Technical Challenges

- Supabase schema design needed multiple connected tables.
- RAG required embedding storage, vector indexing, and match functions.
- Quiz attempts needed correct answer hiding on generation but full answer checking on submission.
- Replanning needed to preserve completed days while changing only pending days.
- Progress dashboards required aggregating quiz data into XP, levels, streaks, heatmaps, badges, and weak-topic lists.
- Frontend needed separate flows for onboarding, dashboard, study room, quiz, result, and profile.
- Local fallback logic was needed when external knowledge or RAG retrieval was unavailable.

---

## Slide 26: Limitations

Current limitations:

- Initial exam coverage is focused mainly on aptitude and reasoning foundation.
- Quality depends on seeded syllabus, quiz templates, and lesson material.
- Some fallback content may be simpler than expert-created content.
- The system currently uses short study durations.
- Advanced proctoring, mentor dashboards, and collaborative learning are not yet included.
- Reminder workflow depends on external n8n configuration.

---

## Slide 27: Future Scope

Future improvements:

- Add more exams and subject domains.
- Add full mentor/admin dashboard.
- Add voice-based teaching and doubt solving.
- Add deeper analytics for institutions.
- Add AI-generated question variations with quality checks.
- Add spaced repetition scheduling.
- Add WhatsApp and Telegram reminders.
- Add peer leaderboard and group challenges.
- Add downloadable reports for learners and institutions.
- Add multilingual learning support.

---

## Slide 28: Conclusion

AI-SAATHI converts exam preparation into a personalized, measurable, and adaptive learning journey.

It solves the key student problem: not knowing what to study, how to practice, and how to improve after mistakes.

By combining AI planning, guided lessons, adaptive quizzes, progress analytics, gamification, Supabase-backed persistence, RAG, and reminder automation, AI-SAATHI becomes more than a study app. It becomes a complete learning companion.

---

## Slide 29: One-Line Pitch

AI-SAATHI is an adaptive AI study companion that creates a personalized plan, teaches daily lessons, tests understanding, tracks weak areas, and automatically adjusts the learning path.

---

## Slide 30: Thank You

### Thank You

Questions?

