from __future__ import annotations

import asyncio
import uuid

import streamlit as st

from agents import run_study_task
from study_core import (
    EXAMS,
)


APP_TITLE = "AI Study Companion"
APP_ICON = "🧠"


CSS = """
<style>
html, body, [class*="css"] { background:#0d0f14; color:#e8e6e0; }
#MainMenu, footer, header { visibility:hidden; }
.block-container { padding:1.5rem 2rem 4rem; max-width:1200px; }
section[data-testid="stSidebar"] { background:#13161f; border-right:1px solid #1e2230; }
.card { background:#13161f; border:1px solid #1e2230; border-radius:10px; padding:1.1rem 1.3rem; margin-bottom:.8rem; }
.metric-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:1rem; margin-bottom:1.2rem; }
.metric-box { background:#13161f; border:1px solid #1e2230; border-radius:10px; padding:1rem; text-align:center; }
.metric-val { font-size:1.8rem; font-weight:700; color:#f59e0b; }
.metric-lbl { color:#6b7280; font-size:.72rem; text-transform:uppercase; letter-spacing:.06em; }
.chip { display:inline-block; background:#1e2230; color:#9ca3af; border-radius:20px; padding:2px 10px; font-size:.72rem; margin-right:4px; }
.chip-gold { background:#2e2008; color:#f59e0b; }
.chip-green { background:#0a2218; color:#34d399; }
.chip-red { background:#2e0d0d; color:#f87171; }
.trace-line { font-family:monospace; font-size:.78rem; color:#6b7280; padding:2px 0; }
.trace-action { color:#34d399; }
.trace-done { color:#f59e0b; font-weight:700; }
.score-ring { width:84px; height:84px; border-radius:50%; border:6px solid #f59e0b; display:flex; align-items:center; justify-content:center; font-size:1.3rem; font-weight:700; color:#f59e0b; margin:auto; }
</style>
"""


def _state() -> None:
    defaults = {
        "screen": "setup",
        "user_id": f"user-{uuid.uuid4().hex[:8]}",
        "user_name": "Aryan Sharma",
        "exam": "SSC CGL",
        "level": "beginner",
        "duration": 5,
        "plan": None,
        "current_day_idx": 0,
        "teaching_topic": None,
        "quiz": None,
        "quiz_answers": {},
        "quiz_question_index": 0,
        "quiz_submitted": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _go(screen: str) -> None:
    st.session_state.screen = screen
    st.rerun()


def _load_plan() -> dict | None:
    if st.session_state.plan:
        return st.session_state.plan
    try:
        result = run_study_task("get_plan", user_id=st.session_state.user_id)
    except Exception:
        return None
    st.session_state.plan = result["plan"]
    return result["plan"]


def _sidebar() -> None:
    with st.sidebar:
        st.header(f"{APP_ICON} {APP_TITLE}")
        st.caption("Planner, teacher, quiz, and progress analyzer running locally.")
        if st.button("Setup", use_container_width=True):
            _go("setup")
        if st.button("Study Plan", use_container_width=True):
            _go("plan")
        if st.button("Progress", use_container_width=True):
            _go("progress")
        st.divider()
        st.text_input("User ID", value=st.session_state.user_id, disabled=True)
        if st.button("New Learner", use_container_width=True):
            for key in ["plan", "teaching_topic", "quiz", "quiz_answers", "quiz_submitted"]:
                st.session_state.pop(key, None)
            st.session_state.user_id = f"user-{uuid.uuid4().hex[:8]}"
            st.session_state.screen = "setup"
            st.rerun()


def _render_setup() -> None:
    st.markdown("## Build a Study Plan")
    col_a, col_b = st.columns([2, 1])
    with col_a:
        with st.form("setup"):
            name = st.text_input("Your name", value=st.session_state.user_name)
            exam = st.selectbox("Target exam", list(EXAMS.keys()), index=list(EXAMS).index(st.session_state.exam))
            level = st.selectbox("Current level", ["beginner", "intermediate", "advanced"], index=["beginner", "intermediate", "advanced"].index(st.session_state.level))
            duration = st.slider("Study duration", 2, 7, st.session_state.duration)
            submitted = st.form_submit_button("Create Plan", type="primary")
        if submitted:
            result = run_study_task(
                "build_plan",
                user_id=st.session_state.user_id,
                exam_id_or_name=exam,
                duration_days=duration,
                name=name,
                level=level,
            )
            plan = result["plan"]
            st.session_state.user_name = name
            st.session_state.exam = exam
            st.session_state.level = level
            st.session_state.duration = duration
            st.session_state.plan = plan
            st.session_state.current_day_idx = 0
            _go("plan")
    with col_b:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### Available Topics")
        topics = run_study_task("list_topics", exam_id_or_name=st.session_state.exam)["topics"]
        for topic in topics:
            st.markdown(f"- **{topic['name']}** · {topic['subject']}")
        st.markdown("</div>", unsafe_allow_html=True)


def _render_plan() -> None:
    plan = _load_plan()
    if not plan:
        st.info("Create a plan first.")
        if st.button("Go to Setup", type="primary"):
            _go("setup")
        return
    taught = sum(1 for day in plan["days"] if day["status"] == "taught")
    st.markdown(f"## Study Plan · {plan['exam']}")
    st.markdown(
        f"""
        <div class="metric-grid">
            <div class="metric-box"><div class="metric-val">{plan['duration']}</div><div class="metric-lbl">Days</div></div>
            <div class="metric-box"><div class="metric-val">{taught}</div><div class="metric-lbl">Taught</div></div>
            <div class="metric-box"><div class="metric-val">{plan['duration'] - taught}</div><div class="metric-lbl">Remaining</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.progress(taught / plan["duration"])
    for index, day in enumerate(plan["days"]):
        active = index == st.session_state.current_day_idx and day["status"] == "pending"
        chip = "chip-green" if day["status"] == "taught" else "chip-gold" if active else ""
        st.markdown('<div class="card">', unsafe_allow_html=True)
        left, right = st.columns([4, 2])
        with left:
            st.markdown(f"### Day {day['day_number']}: {day['topic_name']}")
            st.markdown(
                f'<span class="chip {chip}">{day["status"].upper()}</span>'
                f'<span class="chip">{day["subject"]}</span>'
                f'<span class="chip">{day["allocated_minutes"]} min</span>',
                unsafe_allow_html=True,
            )
        with right:
            if st.button("Teach", key=f"teach-{day['id']}", disabled=day["status"] == "taught", use_container_width=True):
                st.session_state.teaching_topic = day
                _go("teach")
            if st.button("Quiz", key=f"quiz-{day['id']}", use_container_width=True):
                st.session_state.teaching_topic = day
                st.session_state.quiz = None
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = None
                _go("quiz")
        st.markdown("</div>", unsafe_allow_html=True)


def _render_teach() -> None:
    day = st.session_state.teaching_topic
    if not day:
        _go("plan")
    st.markdown(f"## Lesson · {day['topic_name']}")
    with st.expander("Teacher Agent Trace", expanded=True):
        st.markdown('<div class="trace-line">THOUGHT Load plan day and learner level.</div>', unsafe_allow_html=True)
        st.markdown('<div class="trace-line trace-action">ACTION Retrieve topic concepts and examples.</div>', unsafe_allow_html=True)
        st.markdown('<div class="trace-line trace-done">DONE Lesson generated and teaching log persisted.</div>', unsafe_allow_html=True)
    lesson = run_study_task(
        "lesson_for_topic",
        topic_name=day["topic_name"],
        level=st.session_state.level,
    )["lesson_content"]
    st.markdown(f'<div class="card">{lesson}</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Mark Taught and Quiz", type="primary", use_container_width=True):
            run_study_task("teach_day", plan_day_id=day["id"], user_id=st.session_state.user_id)
            st.session_state.plan = run_study_task(
                "get_plan",
                user_id=st.session_state.user_id,
            )["plan"]
            st.session_state.quiz = None
            st.session_state.quiz_answers = {}
            _go("quiz")
    with col_b:
        if st.button("Back to Plan", use_container_width=True):
            _go("plan")


def _render_quiz() -> None:
    day = st.session_state.teaching_topic or (_load_plan() or {}).get("days", [None])[0]
    if not day:
        _go("plan")
    if not st.session_state.quiz:
        st.session_state.quiz = run_study_task(
            "generate_quiz",
            user_id=st.session_state.user_id,
            topic_id=day["topic_id"],
            num_questions=5,
            difficulty=day.get("difficulty", 3),
            plan_day_id=day["id"],
        )
        st.session_state.quiz_answers = {}
        st.session_state.quiz_question_index = 0
        st.session_state.quiz_submitted = None
    quiz = st.session_state.quiz
    question_index = min(st.session_state.quiz_question_index, max(0, quiz["total"] - 1))
    question = quiz["questions"][question_index]
    st.markdown(f"## Quiz · {day['topic_name']}")
    st.caption(f"Question {question_index + 1} of {quiz['total']}")
    if quiz.get("adaptive_context"):
        context = quiz["adaptive_context"]
        st.info(
            f"Personalized from Supabase history: difficulty {context.get('adapted_difficulty', 3)}/5 "
            f"from {context.get('attempts', 0)} saved question attempts."
        )
    st.markdown('<div class="card">', unsafe_allow_html=True)
    choice = st.radio(
        question["question_text"],
        question["options"],
        index=st.session_state.quiz_answers.get(question_index),
        key=f"q-{quiz['attempt_id']}-{question_index}",
    )
    if choice is not None:
        st.session_state.quiz_answers[question_index] = question["options"].index(choice)
    st.markdown("</div>", unsafe_allow_html=True)
    if not st.session_state.quiz_submitted:
        col_prev, col_next, col_finish = st.columns(3)
        with col_prev:
            if st.button("Previous", disabled=question_index == 0):
                st.session_state.quiz_question_index = question_index - 1
                st.rerun()
        with col_next:
            if st.button(
                "Next Question",
                disabled=question_index >= quiz["total"] - 1 or question_index not in st.session_state.quiz_answers,
            ):
                st.session_state.quiz_question_index = question_index + 1
                st.rerun()
        with col_finish:
            if st.button("Finish Quiz", type="primary", disabled=len(st.session_state.quiz_answers) < quiz["total"]):
                st.session_state.quiz_submitted = run_study_task(
                    "submit_quiz",
                    attempt_id=quiz["attempt_id"],
                    user_answers=[st.session_state.quiz_answers[i] for i in range(quiz["total"])],
                    time_taken_secs=300,
                )
                st.rerun()
    else:
        result = st.session_state.quiz_submitted
        pct = int(result["accuracy"])
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown(f'<div class="score-ring">{pct}%</div>', unsafe_allow_html=True)
        with col_b:
            st.metric("Score", f"{result['score']}/{result['total']}")
        with col_c:
            st.metric("Weakness", f"{result['new_weakness_score']:.1f}")
        if result["replan_triggered"]:
            st.warning("Replan triggered because this topic stayed below 40% accuracy.")
        col_1, col_2 = st.columns(2)
        with col_1:
            if st.button("Back to Plan", type="primary", use_container_width=True):
                st.session_state.quiz = None
                st.session_state.quiz_submitted = None
                st.session_state.quiz_question_index = 0
                st.session_state.plan = run_study_task(
                    "get_plan",
                    user_id=st.session_state.user_id,
                )["plan"]
                _go("plan")
        with col_2:
            if st.button("View Progress", use_container_width=True):
                _go("progress")


def _render_progress() -> None:
    st.markdown("## Progress Dashboard")
    data = run_study_task("get_progress", user_id=st.session_state.user_id)
    stats = data["topic_stats"]
    if not stats:
        st.info("Complete one quiz to see progress.")
        return
    total_attempts = sum(row["attempts"] for row in stats)
    total_correct = sum(row["correct"] for row in stats)
    avg = round(total_correct * 100 / total_attempts, 1) if total_attempts else 0
    st.markdown(
        f"""
        <div class="metric-grid">
            <div class="metric-box"><div class="metric-val">{len(stats)}</div><div class="metric-lbl">Topics</div></div>
            <div class="metric-box"><div class="metric-val">{avg}%</div><div class="metric-lbl">Accuracy</div></div>
            <div class="metric-box"><div class="metric-val">{total_attempts}</div><div class="metric-lbl">Questions</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for row in stats:
        color = "chip-red" if row["weakness_score"] >= 60 else "chip-gold" if row["weakness_score"] >= 40 else "chip-green"
        st.markdown(
            f"""
            <div class="card">
              <strong>{row['topic_name']}</strong>
              <span class="chip {color}">weakness {row['weakness_score']:.1f}</span>
              <span class="chip">{row['accuracy']:.0f}% accuracy</span>
              <span class="chip">{row['attempts']} attempts</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if st.button("Request Re-Plan", type="primary"):
        result = run_study_task("replan", user_id=st.session_state.user_id)
        st.session_state.plan = run_study_task("get_plan", user_id=st.session_state.user_id)["plan"]
        st.success(result["message"])


async def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    _state()
    _sidebar()
    screen = st.session_state.screen
    if screen == "setup":
        _render_setup()
    elif screen == "plan":
        _render_plan()
    elif screen == "teach":
        _render_teach()
    elif screen == "quiz":
        _render_quiz()
    elif screen == "progress":
        _render_progress()
    else:
        _render_setup()


if __name__ == "__main__":
    asyncio.run(main())
