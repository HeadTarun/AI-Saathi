"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
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
  const profile = useMemo(() => getLearnerProfile(), []);
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
  const [activeUserId, setActiveUserId] = useState(profile.userId);
  const startedAtRef = useRef<number>(Date.now());

  const steps = lesson?.lesson_steps?.length
    ? lesson.lesson_steps
    : lesson
      ? [{ id: "lesson", title: lesson.topic_name, kind: "concept", content: lesson.lesson_content }]
      : [];
  const activeStep = steps[stepIndex];
  const answeredCount = Object.keys(answers).length;
  const quizReady = !!quiz && answeredCount === quiz.total;

  async function loadStudyRoom() {
    setLoading(true);
    setError("");
    setTeacherStatus("Preparing your lesson");
    try {
      let selected = getSelectedPlanDay();
      const authProfile = await getCurrentAuthProfile();
      const userId = authProfile?.userId ?? profile.userId;
      setActiveUserId(userId);
      if (!selected) {
        const plan = await getStudyPlan(userId);
        selected = plan.days.find((item) => item.unlocked !== false) ?? plan.days[0] ?? null;
        if (selected) saveSelectedPlanDay(selected);
      }
      if (!selected) throw new Error("Create your study plan before opening the study room.");
      if (selected.unlocked === false) throw new Error(selected.unlock_reason || "Complete the previous day to unlock this lesson.");

      setDay(selected);
      setTeacherStatus(selected.day_number > 1 ? "Reviewing yesterday" : "Building your first concept");
      const data = await teachPlanDay(selected.id, userId);
      setLesson(data);
      setStepIndex(0);
      setMode("lesson");
      setTeacherStatus("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open the study room.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStudyRoom();
  }, []);

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
      setError(err instanceof Error ? err.message : "Could not prepare the quiz.");
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
    <main className="quiz-screen">
      <header className="quiz-nav" aria-label="Study navigation">
        <Link className="brand" href="/" aria-label="AI-SAATHI home">
          <span className="brand-coin" aria-hidden="true" />
          <span>AI-SAATHI</span>
        </Link>
        <Link className="quiz-back-link" href="/dashboard">Dashboard</Link>
        <div className="quiz-nav-stats" aria-label="Study progress">
          <span>{day ? `Day ${day.day_number}` : "Study Room"}</span>
          <span style={{ marginLeft: "1rem" }}>{day?.topic_name ?? "Lesson"}</span>
        </div>
      </header>

      <div className="star-field" aria-hidden="true">
        {Array.from({ length: 28 }, (_, index) => (
          <span key={index} className={`star star-${index + 1}`} />
        ))}
      </div>

      <section className="quiz-stage" aria-labelledby="study-title">
        <div className="assistant-row quiz-assistant" aria-hidden="true">
          <div className="pixel-computer">
            <span className="monitor" />
            <span className="face" />
            <span className="base" />
          </div>
          <div className="speech-bubble">
            {loading ? teacherStatus : mode === "lesson" ? "Go step by step. I will teach first, then quiz." : "Lock your answers when ready."}
          </div>
        </div>

        {error && !lesson ? (
          <div className="quiz-card" style={{ textAlign: "center" }}>
            <h1>Study Room</h1>
            <p style={{ color: "#ffb4b4", marginBottom: "1rem" }}>{error}</p>
            <Link href="/dashboard" className="roadmap-button">Back to Dashboard</Link>
          </div>
        ) : loading ? (
          <div className="quiz-card" style={{ textAlign: "center" }}>
            <p className="result-kicker">Teacher</p>
            <h1>{teacherStatus}</h1>
          </div>
        ) : (
          <>
            {mode === "lesson" && lesson && activeStep ? (
              <section className="quiz-card" aria-labelledby="study-title">
                <div className="quiz-card-header">
                  <p>{day?.topic_name}</p>
                  <span>{stepIndex + 1}/{steps.length}</span>
                </div>
                <h1 id="study-title">Teacher Session</h1>
                <div className="lp-endpoint-buttons" style={{ marginBottom: "1rem" }}>
                  {steps.map((item, index) => (
                    <button
                      key={item.id}
                      className={`lp-endpoint-button ${stepIndex === index ? "active" : ""}`}
                      type="button"
                      onClick={() => setStepIndex(index)}
                    >
                      {item.title}
                    </button>
                  ))}
                </div>
                <div className="question-panel" style={{ textAlign: "left" }}>
                  <p className="question-kicker">{activeStep.kind}</p>
                  <h2>{activeStep.title}</h2>
                  <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.75, margin: 0 }}>{activeStep.content}</p>
                  {activeStep.checkpoint ? (
                    <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, marginTop: "1rem", opacity: 0.82 }}>{activeStep.checkpoint}</p>
                  ) : null}
                </div>
                {lesson.personalization ? (
                  <div className="reward-grid" style={{ marginTop: "1rem" }} aria-label="Supabase personalization">
                    <span>
                      <strong>{Math.round(lesson.personalization.accuracy)}%</strong>
                      DB accuracy
                    </span>
                    <span>
                      <strong>{Math.round(lesson.personalization.weakness_score)}</strong>
                      Focus score
                    </span>
                  </div>
                ) : null}
                <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem", flexWrap: "wrap" }}>
                  <button
                    className="quiz-primary-button"
                    type="button"
                    onClick={() => setStepIndex((current) => Math.min(steps.length - 1, current + 1))}
                    disabled={stepIndex === steps.length - 1}
                  >
                    Next
                  </button>
                  <button className="quiz-primary-button" type="button" onClick={startQuiz}>
                    Start Quiz Battle
                  </button>
                </div>
              </section>
            ) : null}

            {mode === "quiz" ? (
              <QuizPanel
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
              <ResultPanel
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

      <div className="moon-band moon-left" aria-hidden="true" />
      <div className="moon-band moon-right" aria-hidden="true" />
    </main>
  );
}

function QuizPanel({
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
    <section className="quiz-card" aria-labelledby="quiz-title">
      <div className="quiz-card-header">
        <p>Quiz Battle</p>
        <span>{quiz ? `${Object.keys(answers).length}/${quiz.total}` : "Loading"}</span>
      </div>
      <h1 id="quiz-title">Show What You Learned</h1>
      {!quiz ? (
        <p style={{ textAlign: "center", padding: "2rem", opacity: 0.7 }}>Preparing questions...</p>
      ) : (
        <>
          {quiz.adaptive_context ? (
            <div className="explanation-panel" style={{ marginBottom: "1rem" }}>
              <strong>Adapted by Supabase history</strong>
              <p>
                Difficulty {quiz.adaptive_context.adapted_difficulty}/5 from {quiz.adaptive_context.attempts} saved question attempts.
              </p>
            </div>
          ) : null}
          {activeQuestion ? (
            <div className="question-panel" style={{ textAlign: "left" }}>
              <p className="question-kicker">Question {questionIndex + 1} of {quiz.total}</p>
              <h2>{activeQuestion.question_text}</h2>
              <div className="option-grid" role="list" aria-label={`Question ${questionIndex + 1} answers`}>
                {activeQuestion.options.map((option, optionIndex) => (
                  <button
                    key={option}
                    className={`option-button ${answers[questionIndex] === optionIndex ? "selected" : ""}`}
                    type="button"
                    onClick={() => chooseAnswer(questionIndex, optionIndex)}
                  >
                    <span>{String.fromCharCode(65 + optionIndex)}.</span>
                    {option}
                  </button>
                ))}
              </div>
            </div>
          ) : null}
          {error ? <p role="alert" style={{ color: "#ffb4b4", marginTop: "1rem" }}>{error}</p> : null}
          <div style={{ display: "flex", gap: "0.75rem", marginTop: "1rem", flexWrap: "wrap" }}>
            <button className="quiz-secondary-button" type="button" onClick={() => setQuestionIndex(questionIndex - 1)} disabled={!canGoBack || submitting}>
              Previous
            </button>
            {canGoNext ? (
              <button
                className="quiz-primary-button"
                type="button"
                onClick={() => setQuestionIndex(questionIndex + 1)}
                disabled={!hasAnswer || submitting}
              >
                Next Question
              </button>
            ) : (
              <button className="quiz-primary-button" type="button" onClick={submitQuiz} disabled={!quizReady || submitting}>
                {submitting ? "Checking answers..." : "Finish Quiz"}
              </button>
            )}
          </div>
        </>
      )}
    </section>
  );
}

function ResultPanel({
  result,
  retry,
  revise,
}: Readonly<{
  result: QuizSubmitResponse;
  retry: () => void;
  revise: () => void;
}>) {
  return (
    <section className="quiz-card result-card" aria-labelledby="result-title">
      <p className="result-kicker">Quest Complete</p>
      <h1 id="result-title">{result.passed ? "Next Day Unlocked" : "Revise And Retry"}</h1>
      <div className="score-orb" aria-label={`Score ${result.score} out of ${result.total}`}>
        <span>{result.score}</span>
        <small>/{result.total}</small>
      </div>
      <div className="reward-grid">
        <span>
          <strong>{Math.round(result.accuracy)}%</strong>
          Accuracy
        </span>
        <span>
          <strong>{result.pass_mark}%</strong>
          Goal
        </span>
      </div>
      <div className="explanation-panel" role="status">
        <strong>{result.passed ? "Great work" : "Stay on this day"}</strong>
        <p>
          {result.passed
            ? "Your next study day is ready on the Dashboard."
            : result.replan_triggered
              ? "Supabase flagged this topic for replanning. Revise the lesson and retry the quiz."
              : "Revise the lesson and retry the quiz to unlock the next day."}
        </p>
      </div>
      <div className="result-actions">
        <button className="quiz-primary-button" type="button" onClick={result.passed ? retry : revise}>
          {result.passed ? "Practice Again" : "Revise Lesson"}
        </button>
        <button className="quiz-secondary-button" type="button" onClick={retry}>
          Retry Quiz
        </button>
        <Link className="quiz-secondary-button" href="/dashboard">
          Dashboard
        </Link>
      </div>
    </section>
  );
}
