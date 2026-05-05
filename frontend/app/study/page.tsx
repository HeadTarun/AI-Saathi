"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  generateStudyQuiz,
  getLearnerProfile,
  getSelectedPlanDay,
  getStudyPlan,
  PlanDay,
  QuizGenerateResponse,
  QuizSubmitResponse,
  saveSelectedPlanDay,
  submitStudyQuiz,
  teachPlanDay,
  TeachResponse,
} from "@/lib/api";
import { getCurrentAuthProfile } from "@/lib/supabase";
import soundManager from "@/utils/soundManager";

type StudyMode = "lesson" | "quiz" | "result";

export default function StudyPage() {
  const [day, setDay] = useState<PlanDay | null>(null);
  const [lesson, setLesson] = useState<TeachResponse | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [quiz, setQuiz] = useState<QuizGenerateResponse | null>(null);
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const [questionIndex, setQuestionIndex] = useState(0);
  const [result, setResult] = useState<QuizSubmitResponse | null>(null);
  const [mode, setMode] = useState<StudyMode>("lesson");
  const [loading, setLoading] = useState(true);
  const [teacherStatus, setTeacherStatus] = useState("Preparing your lesson");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [activeUserId, setActiveUserId] = useState("");
  const startedAtRef = useRef<number>(0);

  const steps = lesson?.lesson_steps?.length
    ? lesson.lesson_steps
    : lesson
      ? [{ id: "lesson", title: lesson.topic_name, kind: "concept", content: lesson.lesson_content }]
      : [];
  const activeStep = steps[stepIndex];
  const answeredCount = Object.keys(answers).length;
  const quizReady = !!quiz && answeredCount === quiz.total;
  const arenaProgress = steps.length ? Math.round(((stepIndex + 1) / steps.length) * 100) : 0;

  const loadStudyRoom = useCallback(async () => {
    setLoading(true);
    setError("");
    setTeacherStatus("Preparing your lesson");
    try {
      let selected = getSelectedPlanDay();
      const authProfile = await getCurrentAuthProfile();
      const localProfile = getLearnerProfile();
      const googleUserId = !authProfile && localProfile.userId.startsWith("google-") ? localProfile.userId : "";

      if (!authProfile && !googleUserId) {
        window.location.href = "/login?next=/study";
        return;
      }

      const userId = authProfile?.userId || googleUserId;
      setActiveUserId(userId);
      if (!selected) {
        const plan = await getStudyPlan(userId);
        selected = plan.days.find((item) => item.unlocked !== false) ?? plan.days[0] ?? null;
        if (selected) saveSelectedPlanDay(selected);
      }
      if (!selected) throw new Error("Create your study plan before opening the study arena.");
      if (selected.unlocked === false) throw new Error(selected.unlock_reason || "Complete the previous day to unlock this lesson.");

      setDay(selected);
      setTeacherStatus(selected.day_number > 1 ? "Scanning yesterday's weak links" : "Building your first arena card");
      const data = await teachPlanDay(selected.id, userId);
      setLesson(data);
      setStepIndex(0);
      setMode("lesson");
      setTeacherStatus("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open the study arena.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void loadStudyRoom();
    }, 0);
    return () => window.clearTimeout(id);
  }, [loadStudyRoom]);

  async function startQuiz() {
    if (!day) return;
    setMode("quiz");
    setError("");
    setQuiz(null);
    setResult(null);
    setAnswers({});
    setQuestionIndex(0);
    startedAtRef.current = Date.now();
    try {
      const data = await generateStudyQuiz(activeUserId, day, 5);
      setQuiz(data);
      setQuestionIndex(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not prepare the quiz battle.");
    }
  }

  function chooseAnswer(questionIndex: number, optionIndex: number) {
    if (result) return;
    soundManager.play("click");
    setAnswers((current) => ({ ...current, [questionIndex]: optionIndex }));
  }

  async function submitQuiz() {
    if (!quiz || !quizReady) return;
    setSubmitting(true);
    setError("");
    try {
      const orderedAnswers = quiz.questions.map((_, index) => answers[index]);
      const elapsedSecs = (Date.now() - startedAtRef.current) / 1000;
      const data = await submitStudyQuiz(quiz.attempt_id, orderedAnswers, elapsedSecs);
      setResult(data);
      setMode("result");
      soundManager.play(data.passed ? "levelup" : "error");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not check your answers.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="study-arena-shell">
      <ArenaNav />

      <section className="study-arena-grid" aria-labelledby="study-title">
        <aside className="arena-side">
          <ArenaMentor
            loading={loading}
            status={teacherStatus}
            mode={mode}
            day={day}
            progress={mode === "lesson" ? arenaProgress : quiz ? Math.round((answeredCount / quiz.total) * 100) : 0}
          />
          <ArenaMissionPanel day={day} mode={mode} />
        </aside>

        <section className="arena-main-stage">
          {error && !lesson ? (
            <div className="arena-empty-state">
              <p className="quest-kicker">Arena Locked</p>
              <h1>Study arena</h1>
              <p>{error}</p>
              <Link href="/dashboard">Back to Quest Map</Link>
            </div>
          ) : loading ? (
            <div className="arena-empty-state">
              <p className="quest-kicker">AI Mentor</p>
              <h1>{teacherStatus}</h1>
            </div>
          ) : (
            <>
              {mode === "lesson" && lesson && activeStep ? (
                <LessonArena
                  steps={steps}
                  stepIndex={stepIndex}
                  setStepIndex={setStepIndex}
                  activeStep={activeStep}
                  lesson={lesson}
                  day={day}
                  startQuiz={startQuiz}
                />
              ) : null}

              {mode === "quiz" ? (
                <BossQuizBattle
                  quiz={quiz}
                  answers={answers}
                  error={error}
                  submitting={submitting}
                  quizReady={quizReady}
                  questionIndex={questionIndex}
                  setQuestionIndex={setQuestionIndex}
                  chooseAnswer={chooseAnswer}
                  submitQuiz={submitQuiz}
                />
              ) : null}

              {mode === "result" && result ? (
                <XPRewardModal
                  result={result}
                  retry={startQuiz}
                  revise={() => {
                    setMode("lesson");
                    setStepIndex(0);
                  }}
                />
              ) : null}
            </>
          )}
        </section>
      </section>
    </main>
  );
}

function ArenaNav() {
  return (
    <header className="quest-nav arena-nav" aria-label="Study navigation">
      <Link className="quest-brand" href="/">
        <span className="quest-brand-mark">A</span>
        <span>AI-SAATHI</span>
      </Link>
      <nav aria-label="Primary">
        <Link href="/dashboard">Quest Map</Link>
        <Link href="/plan">Plan</Link>
        <Link className="active" href="/study">Arena</Link>
        <Link href="/quiz">Quiz</Link>
        <Link href="/profile">Profile</Link>
      </nav>
      <Link className="quest-primary-action" href="/dashboard">Map</Link>
    </header>
  );
}

function ArenaMentor({
  loading,
  status,
  mode,
  day,
  progress,
}: Readonly<{
  loading: boolean;
  status: string;
  mode: StudyMode;
  day: PlanDay | null;
  progress: number;
}>) {
  const message = loading
    ? status
    : mode === "lesson"
      ? "Read the card, answer the checkpoint in your head, then move. Short reps beat panic scrolling."
      : mode === "quiz"
        ? "Battle mode: choose deliberately. The goal is accuracy first, speed second."
        : "Result is feedback, not judgement. Patch the weak link and go again.";

  return (
    <section className="arena-mentor-card" aria-label="AI mentor panel">
      <div className="ai-mentor-core small" aria-hidden="true">
        <span className="ai-mentor-eye" />
        <span className="ai-mentor-pulse" />
      </div>
      <div>
        <p className="quest-kicker">AI Mentor</p>
        <h2>{day ? `Day ${day.day_number}` : "Study Arena"}</h2>
        <p>{message}</p>
      </div>
      <div className="arena-progress-bar" aria-label={`${progress}% arena progress`}>
        <span style={{ width: `${progress}%` }} />
      </div>
    </section>
  );
}

function ArenaMissionPanel({ day, mode }: Readonly<{ day: PlanDay | null; mode: StudyMode }>) {
  return (
    <section className="arena-mission-panel" aria-label="Daily mission status">
      <p className="quest-kicker">Daily Mission</p>
      <h2>{day?.topic_name ?? "Select a quest"}</h2>
      <div>
        <span>Mode</span>
        <strong>{mode === "lesson" ? "Micro Lesson" : mode === "quiz" ? "Boss Quiz" : "Reward"}</strong>
      </div>
      <div>
        <span>Weak Topic</span>
        <strong>{day?.subject ?? "Pending"}</strong>
      </div>
      <div>
        <span>Reward</span>
        <strong>+180 XP</strong>
      </div>
    </section>
  );
}

function LessonArena({
  steps,
  stepIndex,
  setStepIndex,
  activeStep,
  lesson,
  day,
  startQuiz,
}: Readonly<{
  steps: TeachResponse["lesson_steps"];
  stepIndex: number;
  setStepIndex: (index: number | ((current: number) => number)) => void;
  activeStep: NonNullable<TeachResponse["lesson_steps"]>[number];
  lesson: TeachResponse;
  day: PlanDay | null;
  startQuiz: () => void;
}>) {
  return (
    <section className="lesson-arena" aria-labelledby="study-title">
      <div className="arena-title-row">
        <div>
          <p className="quest-kicker">Focused Study Arena</p>
          <h1 id="study-title">{day?.topic_name ?? lesson.topic_name}</h1>
        </div>
        <button type="button" onClick={startQuiz}>Start Boss Quiz</button>
      </div>

      <div className="lesson-step-tabs" aria-label="Micro lesson steps">
        {steps.map((item, index) => (
          <button
            key={item.id}
            type="button"
            className={stepIndex === index ? "active" : ""}
            onClick={() => setStepIndex(index)}
          >
            <span>{index + 1}</span>
            {item.title}
          </button>
        ))}
      </div>

      <LessonMicroCard step={activeStep} />

      {lesson.personalization ? (
        <div className="lesson-signal-row" aria-label="Personalized study signal">
          <span><strong>{Math.round(lesson.personalization.accuracy)}%</strong> accuracy memory</span>
          <span><strong>{Math.round(lesson.personalization.weakness_score)}</strong> focus score</span>
          <span><strong>{stepIndex + 1}/{steps.length}</strong> cards</span>
        </div>
      ) : null}

      <div className="arena-controls">
        <button
          type="button"
          onClick={() => setStepIndex((current) => Math.max(0, current - 1))}
          disabled={stepIndex === 0}
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => setStepIndex((current) => Math.min(steps.length - 1, current + 1))}
          disabled={stepIndex === steps.length - 1}
        >
          Next Micro-Card
        </button>
        <button type="button" className="primary" onClick={startQuiz}>
          Continue Quest
        </button>
      </div>
    </section>
  );
}

function LessonMicroCard({ step }: Readonly<{ step: NonNullable<TeachResponse["lesson_steps"]>[number] }>) {
  return (
    <article className="lesson-micro-card">
      <div className="micro-card-label">
        <span>{step.kind}</span>
        <b>Micro-card</b>
      </div>
      <h2>{step.title}</h2>
      <p>{step.content}</p>
      {step.checkpoint ? (
        <div className="socratic-checkpoint">
          <span>Socratic checkpoint</span>
          <strong>{step.checkpoint}</strong>
        </div>
      ) : null}
    </article>
  );
}

function BossQuizBattle({
  quiz,
  answers,
  error,
  submitting,
  quizReady,
  questionIndex,
  setQuestionIndex,
  chooseAnswer,
  submitQuiz,
}: Readonly<{
  quiz: QuizGenerateResponse | null;
  answers: Record<number, number>;
  error: string;
  submitting: boolean;
  quizReady: boolean;
  questionIndex: number;
  setQuestionIndex: (questionIndex: number) => void;
  chooseAnswer: (questionIndex: number, optionIndex: number) => void;
  submitQuiz: () => void;
}>) {
  const activeQuestion = quiz?.questions[questionIndex];
  const hasAnswer = answers[questionIndex] !== undefined;
  const canGoBack = questionIndex > 0;
  const canGoNext = !!quiz && questionIndex < quiz.total - 1;

  return (
    <section className="boss-quiz-battle" aria-labelledby="quiz-title">
      <div className="boss-header">
        <div>
          <p className="quest-kicker">Boss Quiz Battle</p>
          <h1 id="quiz-title">Defeat the weak-topic boss</h1>
        </div>
        <div className="boss-health" aria-label={quiz ? `${Object.keys(answers).length} of ${quiz.total} answered` : "Loading battle"}>
          <span style={{ width: quiz ? `${(Object.keys(answers).length / quiz.total) * 100}%` : "8%" }} />
        </div>
      </div>

      {!quiz ? (
        <div className="battle-loading">Summoning readable questions...</div>
      ) : (
        <>
          {quiz.adaptive_context ? (
            <div className="battle-adaptive-note">
              Adapted to difficulty {quiz.adaptive_context.adapted_difficulty}/5 from {quiz.adaptive_context.attempts} saved attempts.
            </div>
          ) : null}
          {activeQuestion ? (
            <article className="battle-question-card">
              <span>Question {questionIndex + 1}/{quiz.total}</span>
              <h2>{activeQuestion.question_text}</h2>
              <div className="battle-option-grid" role="list" aria-label={`Question ${questionIndex + 1} answers`}>
                {activeQuestion.options.map((option, optionIndex) => (
                  <button
                    key={option}
                    className={answers[questionIndex] === optionIndex ? "selected" : ""}
                    type="button"
                    onClick={() => chooseAnswer(questionIndex, optionIndex)}
                  >
                    <b>{String.fromCharCode(65 + optionIndex)}</b>
                    <span>{option}</span>
                  </button>
                ))}
              </div>
            </article>
          ) : null}
          {error ? <p className="quest-alert" role="alert">{error}</p> : null}
          <div className="arena-controls">
            <button type="button" onClick={() => setQuestionIndex(questionIndex - 1)} disabled={!canGoBack || submitting}>
              Previous
            </button>
            {canGoNext ? (
              <button type="button" className="primary" onClick={() => setQuestionIndex(questionIndex + 1)} disabled={!hasAnswer || submitting}>
                Next Strike
              </button>
            ) : (
              <button type="button" className="primary" onClick={submitQuiz} disabled={!quizReady || submitting}>
                {submitting ? "Checking..." : "Finish Battle"}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function XPRewardModal({
  result,
  retry,
  revise,
}: Readonly<{
  result: QuizSubmitResponse;
  retry: () => void;
  revise: () => void;
}>) {
  const earnedXp = result.score * 45 + (result.passed ? 120 : 30);
  return (
    <section className="xp-reward-modal" aria-labelledby="result-title">
      <div className="xp-modal-card">
        <p className="quest-kicker">XP Reward Modal</p>
        <h1 id="result-title">{result.passed ? "Quest Cleared" : "Revision Required"}</h1>
        <div className="xp-orb" aria-label={`${earnedXp} XP earned`}>
          <strong>+{earnedXp}</strong>
          <span>XP</span>
        </div>
        <div className="xp-result-grid">
          <span><strong>{result.score}/{result.total}</strong> score</span>
          <span><strong>{Math.round(result.accuracy)}%</strong> accuracy</span>
          <span><strong>{result.pass_mark}%</strong> unlock mark</span>
        </div>
        <p>
          {result.passed
            ? "Nice. The next node is ready. Review one miss before moving so the win actually sticks."
            : result.replan_triggered
              ? "The radar marked this as a weak topic. Revise the micro-card and retry with a calmer route."
              : "Close attempt. Patch the concept, then take the boss battle again."}
        </p>
        <div className="arena-controls centered">
          <button type="button" className="primary" onClick={result.passed ? retry : revise}>
            {result.passed ? "Practice Again" : "Revise Lesson"}
          </button>
          <button type="button" onClick={retry}>Retry Battle</button>
          <Link href="/dashboard">Quest Map</Link>
        </div>
      </div>
    </section>
  );
}
