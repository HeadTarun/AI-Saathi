"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  clearSelectedPlanDay,
  completeGoogleLogin,
  getLearnerProfile,
  getSupabaseProfile,
  getStudyPlan,
  LEVELS,
  LearnerProfile,
  PlanDay,
  profileFromGoogleLogin,
  saveLearnerProfile,
  saveSelectedPlanDay,
  StudyPlan,
  onboardLearner,
} from "@/lib/api";
import { getCurrentAuthProfile } from "@/lib/supabase";

const FOUNDATION_EXAM_ID = "aptitude-reasoning-foundation";
const FOUNDATION_GOAL =
  "Create a custom aptitude and reasoning plan using IndiaBix and GeeksforGeeks-style knowledge practice.";

export default function DashboardPage() {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [activeDay, setActiveDay] = useState<PlanDay | null>(null);
  const [profile, setProfile] = useState<LearnerProfile>(() => getLearnerProfile());
  const [loading, setLoading] = useState(true);
  const [customPlanLoading, setCustomPlanLoading] = useState(false);
  const [authStatus, setAuthStatus] = useState("");
  const [error, setError] = useState("");

  const taughtCount = plan?.days.filter((day) => day.status === "taught").length ?? 0;
  const progress = plan?.days.length ? Math.round((taughtCount / plan.days.length) * 100) : 0;
  const nextDay = activeDay ?? plan?.days.find((day) => day.status !== "taught") ?? plan?.days[0] ?? null;
  const totalMinutes = plan?.days.reduce((sum, day) => sum + day.allocated_minutes, 0) ?? 0;
  const remainingCount = plan?.days.filter((day) => day.status !== "taught").length ?? 0;

  async function loadPlan(userId = profile.userId) {
    setLoading(true);
    setError("");
    try {
      const supabaseProfile = await getSupabaseProfile(userId).catch(() => null);
      if (supabaseProfile?.user) {
        setProfile((current) => {
          const nextProfile: LearnerProfile = {
            ...current,
            userId: supabaseProfile.user.id,
            name: supabaseProfile.user.name || current.name,
            level: LEVELS.includes(supabaseProfile.user.level as LearnerProfile["level"])
              ? (supabaseProfile.user.level as LearnerProfile["level"])
              : current.level,
            exam: supabaseProfile.active_plan?.exam_id || current.exam,
            durationDays: supabaseProfile.active_plan?.duration_days || current.durationDays,
          };
          saveLearnerProfile(nextProfile);
          return nextProfile;
        });
      }
      const data = await getStudyPlan(userId);
      setPlan(data);
      setActiveDay((current) => current ?? data.days.find((day) => day.status !== "taught") ?? data.days[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create your study plan to begin.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    async function boot() {
      const authProfile = await getCurrentAuthProfile();
      let nextUserId = profile.userId;
      if (authProfile) {
        const nextProfile: LearnerProfile = {
          ...getLearnerProfile(),
          userId: authProfile.userId,
          name: authProfile.name || profile.name,
          email: authProfile.email,
        };
        saveLearnerProfile(nextProfile);
        setProfile(nextProfile);
        nextUserId = authProfile.userId;
      }

      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const state = params.get("state");

      if (code && state) {
        setAuthStatus("Signing you in with Google...");
        try {
          const googleProfile = await completeGoogleLogin(code, state, `${window.location.origin}/dashboard`);
          const nextProfile = profileFromGoogleLogin(googleProfile);
          saveLearnerProfile(nextProfile);
          setProfile(nextProfile);
          window.history.replaceState({}, "", "/dashboard");
          nextUserId = nextProfile.userId;
        } catch (err) {
          setError(err instanceof Error ? err.message : "Google sign in could not be completed.");
        } finally {
          setAuthStatus("");
        }
      }

      await loadPlan(code && state ? getLearnerProfile().userId : nextUserId);
    }

    void boot();
  }, []);

  function openStudyRoom(day: PlanDay) {
    if (day.unlocked === false) {
      setError(day.unlock_reason || "Complete the previous day to unlock this lesson.");
      return;
    }
    saveSelectedPlanDay(day);
    window.location.assign("/study");
  }

  function handleSelect(day: PlanDay) {
    setActiveDay(day);
    if (day.unlocked === false) {
      setError(day.unlock_reason || "Complete the previous day to unlock this lesson.");
    } else {
      setError("");
    }
  }

  async function createKnowledgeBasePlan() {
    setCustomPlanLoading(true);
    setError("");
    const days = Math.max(2, Math.min(7, Number(profile.durationDays) || 5));
    const nextProfile: LearnerProfile = {
      ...profile,
      exam: FOUNDATION_EXAM_ID,
      durationDays: days,
      userGoal: FOUNDATION_GOAL,
    };

    try {
      saveLearnerProfile(nextProfile);
      clearSelectedPlanDay();
      setProfile(nextProfile);
      await onboardLearner({
        user_id: nextProfile.userId,
        exam_id: FOUNDATION_EXAM_ID,
        duration_days: days,
        name: nextProfile.name,
        email: nextProfile.email,
        level: nextProfile.level,
        user_goal: FOUNDATION_GOAL,
      });
      await loadPlan(nextProfile.userId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the custom knowledge-base plan.");
    } finally {
      setCustomPlanLoading(false);
    }
  }

  return (
    <main className="learn-page dashboard-alive-page">
      <DashboardNav />
      <DashboardAmbience />
      <section className="learn-hero" aria-labelledby="dashboard-title">
        <div className="world-art" aria-hidden="true">
          <div className="sky-grid" />
          <div className="sun" />
          <div className="planet-ring" />
          <div className="far-mountain far-one" />
          <div className="far-mountain far-two" />
          <div className="world-dome" />
          <div className="island island-left">
            <span className="tower" />
            <span className="tree tree-a" />
            <span className="tree tree-b" />
          </div>
          <div className="mountain-cluster">
            <span className="peak peak-one" />
            <span className="peak peak-two" />
            <span className="bridge" />
          </div>
          <div className="floating-campus">
            <span className="campus-gem" />
            <span className="campus-base" />
            <span className="campus-ray ray-one" />
            <span className="campus-ray ray-two" />
          </div>
          <div className="hero-cloud cloud-one" />
          <div className="hero-cloud cloud-two" />
        </div>

        <div className="hero-copy">
          <p>Welcome back, {profile.name}</p>
          <h1 id="dashboard-title">Dashboard</h1>
          <p>Follow your daily plan, open lessons, and enter quiz battles from one place.</p>
          <a className="hero-cta" href="#study-plan">View Plan</a>
        </div>
      </section>

      <section className="dash-command-deck" aria-label="Dashboard command center">
        <div className="dash-assistant-card pixel-panel">
          <div className="dash-robot" aria-hidden="true">
            <span className="dash-robot-antenna" />
            <span className="dash-robot-head" />
            <span className="dash-robot-face" />
            <span className="dash-robot-body" />
            <span className="dash-robot-jet" />
          </div>
          <div className="dash-speech">
            <span>AI-SAATHI LIVE</span>
            <strong>{nextDay ? `Next quest: Day ${nextDay.day_number}` : "Build your first quest"}</strong>
            <p>{nextDay ? nextDay.topic_name : "Create a plan and your learning map will light up here."}</p>
            <button
              className="dash-custom-plan-button"
              type="button"
              onClick={createKnowledgeBasePlan}
              disabled={customPlanLoading}
            >
              {customPlanLoading ? "Building..." : "Custom Plan: IndiaBix + Geeks"}
            </button>
          </div>
        </div>

        <div className="dash-status-grid" aria-label="Learning status">
          <StatusTile label="Plan Power" value={`${progress}%`} tone="cyan" />
          <StatusTile label="Days Left" value={plan ? String(remainingCount) : "--"} tone="gold" />
          <StatusTile label="Minutes" value={plan ? String(totalMinutes) : "--"} tone="mint" />
          <StatusTile label="Level" value={profile.level} tone="pink" />
        </div>
      </section>

      <section className="track-section" id="study-plan" aria-labelledby="plan-heading">
        <div className="section-kicker">Your Study Run</div>
        <div className="section-heading-row">
          <div>
            <h2 id="plan-heading">{plan ? `${plan.exam} Plan` : "Study Plan"}</h2>
            <p>
              Complete each day in order, revise weak areas, and keep your preparation moving.
            </p>
          </div>
          <div className="player-stats" aria-label="Study plan summary">
            <span>{profile.level}</span>
            <span>{plan?.duration_days ?? profile.durationDays} days</span>
            <span>{progress}% done</span>
          </div>
        </div>

        {loading ? (
          <div className="roadmap-panel" style={{ maxWidth: 720, margin: "0 auto" }}>
            <h3>{authStatus || "Loading your plan..."}</h3>
          </div>
        ) : error && !plan ? (
          <div className="roadmap-panel" style={{ maxWidth: 720, margin: "0 auto" }}>
            <h3>Start with setup</h3>
            <p>{error}</p>
            <div className="dashboard-plan-actions">
              <Link className="roadmap-button" href="/plan">Create Study Plan</Link>
              <button
                className="roadmap-button"
                type="button"
                onClick={createKnowledgeBasePlan}
                disabled={customPlanLoading}
              >
                {customPlanLoading ? "Building..." : "Custom Knowledge Plan"}
              </button>
            </div>
          </div>
        ) : plan ? (
          <div className="track-layout">
            <div className="track-grid">
              {plan.days.map((day) => (
                <PlanDayCard
                  key={day.id}
                  day={day}
                  selected={activeDay?.id === day.id}
                  onSelect={() => handleSelect(day)}
                  onStudy={() => openStudyRoom(day)}
                />
              ))}
            </div>

            <aside className="roadmap-panel dashboard-side-panel" aria-label="Selected study day">
              <div className="roadmap-orb" aria-hidden="true" />
              <div className="dash-mini-scanner" aria-hidden="true">
                {plan.days.slice(0, 18).map((day) => (
                  <span
                    key={day.id}
                    className={day.status === "taught" ? "complete" : day.unlocked === false ? "locked" : "ready"}
                  />
                ))}
              </div>
              <p className="section-kicker">Active Day</p>
              <h3>{activeDay ? `Day ${activeDay.day_number}: ${activeDay.topic_name}` : "Choose a day"}</h3>
              <p>
                {activeDay
                  ? `${activeDay.subject} · ${activeDay.allocated_minutes} minutes · difficulty ${activeDay.difficulty}/5`
                  : "Select a day from your plan to begin."}
              </p>
              {activeDay ? (
                <>
                  <button
                    className="roadmap-button"
                    type="button"
                    onClick={() => openStudyRoom(activeDay)}
                    disabled={activeDay.unlocked === false}
                  >
                    {activeDay.unlocked === false ? "Locked" : "Open Study Room"}
                  </button>
                  <button
                    className="roadmap-button"
                    type="button"
                    onClick={() => openStudyRoom(activeDay)}
                    style={{ marginTop: "0.5rem", width: "100%" }}
                  >
                    Lesson And Quiz
                  </button>
                </>
              ) : null}
              {error && plan ? <p role="alert" style={{ color: "#ffb4b4", marginTop: "1rem" }}>{error}</p> : null}
            </aside>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function DashboardAmbience() {
  return (
    <>
      <div className="dash-stars" aria-hidden="true">
        {Array.from({ length: 24 }, (_, index) => (
          <span key={index} className={`dash-star dash-star-${index + 1}`} />
        ))}
      </div>
      <div className="dash-world-layer" aria-hidden="true">
        <span className="dash-planet dash-planet-one" />
        <span className="dash-planet dash-planet-two" />
        <span className="dash-meteor dash-meteor-one" />
        <span className="dash-meteor dash-meteor-two" />
        <span className="dash-cloud dash-cloud-one" />
        <span className="dash-cloud dash-cloud-two" />
      </div>
    </>
  );
}

function StatusTile({
  label,
  value,
  tone,
}: Readonly<{
  label: string;
  value: string;
  tone: "cyan" | "gold" | "mint" | "pink";
}>) {
  return (
    <div className={`dash-status-tile dash-status-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DashboardNav() {
  return (
    <header className="learn-nav" aria-label="Main navigation">
      <Link className="brand" href="/" aria-label="AI-SAATHI home">
        <span className="brand-coin" aria-hidden="true" />
        <span>AI-SAATHI</span>
      </Link>
      <nav className="learn-links" aria-label="Primary">
        <Link className="active" href="/dashboard">Dashboard</Link>
        <Link href="/plan">Plan</Link>
        <Link href="/study">Study</Link>
        <Link href="/profile">Profile</Link>
      </nav>
      <div className="nav-actions">
        <Link className="signup-link" href="/profile">Profile</Link>
      </div>
    </header>
  );
}

function PlanDayCard({
  day,
  selected,
  onSelect,
  onStudy,
}: Readonly<{
  day: PlanDay;
  selected: boolean;
  onSelect: () => void;
  onStudy: () => void;
}>) {
  const percent = day.status === "taught" ? 100 : 18;
  const palette = day.difficulty >= 4 ? "ai" : day.priority === "HIGH" ? "data" : "python";
  const locked = day.unlocked === false;

  return (
    <article
      className={`track-card ${selected ? "selected" : ""}`}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onSelect();
      }}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
    >
      <span className={`track-art ${palette}`} aria-hidden="true">
        <span className="art-sky" />
        <span className="art-land" />
        <span className="art-marker" />
      </span>
      <span className="track-meta">
        <span>Day {day.day_number}</span>
        <span className={`difficulty ${day.status === "taught" ? "beginner" : "intermediate"}`}>
          {locked ? "Locked" : day.status === "taught" ? "Done" : "Ready"}
        </span>
      </span>
      <span className="track-title">{day.topic_name}</span>
      <span className="track-description">{day.subject || "Study topic"} · {day.allocated_minutes} minutes</span>
      <span className="progress-row">
        <span>{percent}% complete</span>
        <span>{day.best_score ? `${Math.round(day.best_score)}% best` : `Level ${day.difficulty}`}</span>
      </span>
      <span className="progress-track">
        <span style={{ width: `${percent}%` }} />
      </span>
      <span className="badge-chip">{day.priority} priority</span>
      <span style={{ display: "flex", gap: "0.5rem", marginTop: "1rem", position: "relative", zIndex: 2 }}>
        <button className="roadmap-button" type="button" onClick={(event) => { event.stopPropagation(); onStudy(); }} disabled={locked} style={{ padding: "0.55rem 0.8rem" }}>
          {locked ? "Locked" : "Study"}
        </button>
      </span>
      {locked ? <span className="track-description">{day.unlock_reason}</span> : null}
    </article>
  );
}
