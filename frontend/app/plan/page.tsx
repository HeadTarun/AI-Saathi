"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import {
  createCustomRagPlan,
  getLearnerProfile,
  LearnerLevel,
  listStudyGoals,
  onboardLearner,
  saveLearnerProfile,
  StudyGoal,
} from "@/lib/api";
import { getCurrentAuthProfile } from "@/lib/supabase";

const DEFAULT_LEVEL: LearnerLevel = "beginner";
const FOUNDATION_EXAM_ID = "aptitude-reasoning-foundation";
const FOUNDATION_GOAL = "Build aptitude and reasoning basics, then practice quiz-ready shortcuts.";

export default function PlanPage() {
  const [goals, setGoals] = useState<StudyGoal[]>([]);
  const [exam, setExam] = useState("");
  const [level, setLevel] = useState<LearnerLevel>(DEFAULT_LEVEL);
  const [durationDays, setDurationDays] = useState(5);
  const [userGoal, setUserGoal] = useState("");
  const [name, setName] = useState("Learner");
  const [userId, setUserId] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [customLoading, setCustomLoading] = useState(false);
  const [booting, setBooting] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function boot() {
      setBooting(true);
      setError("");
      try {
        const localProfile = getLearnerProfile();
        const authProfile = await getCurrentAuthProfile();
        const googleProfile = localProfile.userId.startsWith("google-") ? localProfile : null;

        if (!authProfile && !googleProfile) {
          setError("Sign in before generating a study plan.");
          return;
        }

        const nextProfile = {
          ...localProfile,
          userId: authProfile?.userId || googleProfile?.userId || localProfile.userId,
          name: authProfile?.name || googleProfile?.name || localProfile.name,
          email: authProfile?.email || googleProfile?.email || localProfile.email,
        };
        saveLearnerProfile(nextProfile);
        setUserId(nextProfile.userId);
        setName(nextProfile.name || "Learner");
        setEmail(nextProfile.email || "");
        setLevel(nextProfile.level || DEFAULT_LEVEL);
        setDurationDays(nextProfile.durationDays || 5);
        setUserGoal(nextProfile.userGoal || "");

        const items = await listStudyGoals();
        setGoals(items);
        const currentGoal = items.find(
          (item) => item.id === nextProfile.exam || item.name === nextProfile.exam
        );
        setExam(currentGoal?.id || items[0]?.id || nextProfile.exam || "");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load available study sources.");
      } finally {
        setBooting(false);
      }
    }

    void boot();
  }, []);

  async function createPlan(selectedExam = exam, selectedGoal = userGoal) {
    setError("");

    if (!userId) {
      setError("Sign in before generating a study plan.");
      return;
    }

    if (!selectedExam) {
      setError("Choose one available Supabase source.");
      return;
    }

    const trimmedGoal = selectedGoal.trim();
    if (!trimmedGoal) {
      setError("Tell the planner your goal before generating a plan.");
      return;
    }

    const days = Math.max(2, Math.min(7, Number(durationDays) || 5));
    setLoading(true);

    try {
      saveLearnerProfile({
        userId,
        name,
        email,
        exam: selectedExam,
        level,
        durationDays: days,
        userGoal: trimmedGoal,
      });

      await onboardLearner({
        user_id: userId,
        exam_id: selectedExam,
        duration_days: days,
        name,
        email,
        level,
        user_goal: trimmedGoal,
      });

      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Planner could not generate your study plan.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await createPlan();
  }

  async function handleFoundationPlan() {
    setExam(FOUNDATION_EXAM_ID);
    setUserGoal((current) => current.trim() || FOUNDATION_GOAL);
    await createPlan(FOUNDATION_EXAM_ID, userGoal.trim() || FOUNDATION_GOAL);
  }

  async function handleCustomRagPlan() {
    setError("");

    if (!userId) {
      setError("Sign in before generating a custom RAG plan.");
      return;
    }

    const trimmedGoal = userGoal.trim();
    if (!trimmedGoal) {
      setError("Tell the custom planner your goal before generating a plan.");
      return;
    }

    const days = Math.max(2, Math.min(7, Number(durationDays) || 5));
    setCustomLoading(true);

    try {
      saveLearnerProfile({
        userId,
        name,
        email,
        exam: "custom-rag",
        level,
        durationDays: days,
        userGoal: trimmedGoal,
      });

      await createCustomRagPlan({
        user_id: userId,
        exam_id: "custom-rag",
        duration_days: days,
        name,
        email,
        level,
        user_goal: trimmedGoal,
      });

      window.location.href = "/dashboard";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Custom RAG planner could not generate your study plan.");
    } finally {
      setCustomLoading(false);
    }
  }

  return (
    <main className="login-screen">
      <header className="site-nav" aria-label="Main navigation">
        <Link className="brand" href="/" aria-label="AI-SAATHI home">
          <span className="brand-coin" aria-hidden="true" />
          <span>AI-SAATHI</span>
        </Link>
        <nav className="nav-links" aria-label="Primary">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/study">Study</Link>
          <Link href="/profile">Profile</Link>
        </nav>
        <Link className="signup-link" href="/login">
          Login
        </Link>
      </header>

      <div className="star-field" aria-hidden="true">
        {Array.from({ length: 28 }, (_, index) => (
          <span key={index} className={`star star-${index + 1}`} />
        ))}
      </div>

      <section className="login-stage signup-stage" aria-labelledby="plan-heading">
        <div className="assistant-row" aria-hidden="true">
          <div className="auth-robot">
            <span className="auth-robot-antenna" />
            <span className="auth-robot-head" />
            <span className="auth-robot-face" />
            <span className="auth-robot-body" />
            <span className="auth-robot-jet" />
          </div>
          <div className="speech-bubble">
            Choose a goal from Supabase and the planner will build your next study run.
          </div>
        </div>

        <form className="login-card signup-card" onSubmit={handleSubmit} noValidate>
          <h1 id="plan-heading">Generate Study Plan</h1>

          <label className="field-label" htmlFor="source">
            Available Source
          </label>
          <select
            id="source"
            name="source"
            value={exam}
            onChange={(event) => setExam(event.target.value)}
            disabled={booting || goals.length === 0}
          >
            {goals.length > 0 ? (
              goals.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))
            ) : (
              <option value="">Loading sources...</option>
            )}
          </select>

          <label className="field-label" htmlFor="level">
            Current Level
          </label>
          <select
            id="level"
            name="level"
            value={level}
            onChange={(event) => setLevel(event.target.value as LearnerLevel)}
            disabled={booting}
          >
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
            <option value="advanced">Advanced</option>
          </select>

          <label className="field-label" htmlFor="duration">
            Plan Length
          </label>
          <input
            id="duration"
            name="duration"
            type="number"
            min={2}
            max={7}
            value={durationDays}
            onChange={(event) => setDurationDays(Number(event.target.value))}
            disabled={booting}
          />

          <label className="field-label" htmlFor="goal">
            Your Goal
          </label>
          <input
            id="goal"
            name="goal"
            type="text"
            placeholder="Example: clear basics, revise weak topics, prepare for mock tests"
            value={userGoal}
            onChange={(event) => setUserGoal(event.target.value)}
            disabled={booting}
          />

          {email ? (
            <p className="account-copy" style={{ lineHeight: 1.8 }}>
              Planner will save this run for {email}.
            </p>
          ) : null}

          {error ? (
            <p className="error-message" role="alert">
              {error}
            </p>
          ) : null}

          {error && !userId ? (
            <Link className="login-button" href="/login" style={{ display: "block", textAlign: "center", textDecoration: "none" }}>
              Go To Login
            </Link>
          ) : (
            <>
              <button className="login-button" type="submit" disabled={loading || booting || !exam}>
                {loading ? "Generating plan..." : booting ? "Loading sources..." : "Generate Plan"}
              </button>
              <button
                className="quiz-secondary-button"
                type="button"
                onClick={handleCustomRagPlan}
                disabled={loading || customLoading || booting}
                style={{ width: "100%", marginTop: "0.75rem" }}
              >
                {customLoading ? "Building custom RAG plan..." : "Generate Custom RAG Plan"}
              </button>
              <button
                className="quiz-secondary-button"
                type="button"
                onClick={handleFoundationPlan}
                disabled={loading || customLoading || booting}
                style={{ width: "100%", marginTop: "0.75rem" }}
              >
                Create Aptitude + Reasoning Plan
              </button>
            </>
          )}
        </form>
      </section>

      <div className="moon-band moon-left" aria-hidden="true" />
      <div className="moon-band moon-right" aria-hidden="true" />
    </main>
  );
}
