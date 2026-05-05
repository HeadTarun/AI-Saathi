"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { CSSProperties } from "react";
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
const DEFAULT_PROFILE: LearnerProfile = {
  userId: "learner-preview",
  name: "Learner",
  exam: "SSC CGL",
  level: "beginner",
  durationDays: 5,
};

export default function DashboardPage() {
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [activeDay, setActiveDay] = useState<PlanDay | null>(null);
  const [profile, setProfile] = useState<LearnerProfile>(DEFAULT_PROFILE);
  const [loading, setLoading] = useState(true);
  const [customPlanLoading, setCustomPlanLoading] = useState(false);
  const [error, setError] = useState("");

  const taughtCount = plan?.days.filter((day) => day.status === "taught").length ?? 0;
  const progress = plan?.days.length ? Math.round((taughtCount / plan.days.length) * 100) : 0;
  const nextDay = activeDay ?? plan?.days.find((day) => day.status !== "taught") ?? plan?.days[0] ?? null;
  const xp = 1250 + taughtCount * 180 + progress * 12;
  const streak = Math.max(1, Math.min(14, taughtCount + 3));
  const level = Math.max(1, Math.floor(xp / 900));
  const weakTopic = plan?.days.find((day) => day.status !== "taught" && day.priority === "HIGH") ?? nextDay;

  const loadPlan = useCallback(async (userId: string) => {
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
  }, []);

  useEffect(() => {
    async function boot() {
      const storedProfile = getLearnerProfile();
      try {
        let nextUserId = storedProfile.userId;
        const params = new URLSearchParams(window.location.search);
        const code = params.get("code");
        const state = params.get("state");

        if (code && state) {
          setLoading(true);
          try {
            const googleProfile = await completeGoogleLogin(code, state, `${window.location.origin}/dashboard`);
            const nextProfile = profileFromGoogleLogin(googleProfile);
            saveLearnerProfile(nextProfile);
            setProfile(nextProfile);
            window.history.replaceState({}, "", "/dashboard");
            await loadPlan(nextProfile.userId);
            return;
          } catch (err) {
            setError(err instanceof Error ? err.message : "Google sign in could not be completed.");
            setLoading(false);
            return;
          }
        }

        const authProfile = await getCurrentAuthProfile();
        if (!authProfile) {
          if (storedProfile.userId.startsWith("google-")) {
            nextUserId = storedProfile.userId;
            await loadPlan(nextUserId);
            return;
          }

          window.location.href = "/login?next=/dashboard";
          return;
        }

        const nextProfile: LearnerProfile = {
          ...storedProfile,
          userId: authProfile.userId,
          name: authProfile.name || storedProfile.name,
          email: authProfile.email,
        };
        saveLearnerProfile(nextProfile);
        setProfile(nextProfile);
        await loadPlan(authProfile.userId);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not verify your Supabase session.");
        setLoading(false);
      }
    }

    const id = window.setTimeout(() => {
      void boot();
    }, 0);
    return () => window.clearTimeout(id);
  }, [loadPlan]);

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
    setError(day.unlocked === false ? day.unlock_reason || "Complete the previous day to unlock this lesson." : "");
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
    <main className="quest-world">
      <QuestNav active="dashboard" />

      <section className="quest-dashboard" aria-labelledby="dashboard-title">
        <div className="quest-dashboard-main">
          <AImentorPanel
            name={profile.name}
            nextDay={nextDay}
            loadingText={loading ? "Syncing your quest map..." : ""}
            onCustomPlan={createKnowledgeBasePlan}
            customPlanLoading={customPlanLoading}
          />

          <DailyQuestCard
            day={nextDay}
            planName={plan?.exam ?? profile.exam}
            progress={progress}
            onContinue={() => nextDay && openStudyRoom(nextDay)}
          />

          <SkillMapPath
            days={plan?.days ?? []}
            activeDay={activeDay}
            onSelect={handleSelect}
            onStudy={openStudyRoom}
            loading={loading}
            error={error}
          />
        </div>

        <aside className="quest-dashboard-rail" aria-label="Learning status">
          <div className="quest-stat-grid">
            <CompactStat label="XP" value={xp.toLocaleString("en-IN")} tone="gold" />
            <CompactStat label="Streak" value={`${streak}d`} tone="mint" />
            <CompactStat label="Level" value={String(level)} tone="cyan" />
            <CompactStat label="Weak Topic" value={weakTopic?.topic_name ?? "--"} tone="rose" />
          </div>
          <WeakAreaRadar days={plan?.days ?? []} weakTopic={weakTopic} />
          <RevisionQueue days={plan?.days ?? []} onStudy={openStudyRoom} />
          <div className="quest-setup-card">
            <span>Custom track</span>
            <strong>IndiaBix + GFG aptitude run</strong>
            <button type="button" onClick={createKnowledgeBasePlan} disabled={customPlanLoading}>
              {customPlanLoading ? "Building..." : "Generate"}
            </button>
          </div>
        </aside>
      </section>

      {error && plan ? <p className="quest-alert" role="alert">{error}</p> : null}
    </main>
  );
}

function QuestNav({ active }: Readonly<{ active: "dashboard" | "study" }>) {
  return (
    <header className="quest-nav" aria-label="Main navigation">
      <Link className="quest-brand" href="/">
        <span className="quest-brand-mark">A</span>
        <span>AI-SAATHI</span>
      </Link>
      <nav aria-label="Primary">
        <Link className={active === "dashboard" ? "active" : ""} href="/dashboard">Quest Map</Link>
        <Link href="/plan">Plan</Link>
        <Link className={active === "study" ? "active" : ""} href="/study">Arena</Link>
        <Link href="/quiz">Quiz</Link>
        <Link href="/profile">Profile</Link>
      </nav>
      <Link className="quest-primary-action" href="/study">Continue Quest</Link>
    </header>
  );
}

function AImentorPanel({
  name,
  nextDay,
  loadingText,
  onCustomPlan,
  customPlanLoading,
}: Readonly<{
  name: string;
  nextDay: PlanDay | null;
  loadingText: string;
  onCustomPlan: () => void;
  customPlanLoading: boolean;
}>) {
  return (
    <section className="ai-mentor-panel" aria-label="AI mentor panel">
      <div className="ai-mentor-core" aria-hidden="true">
        <span className="ai-mentor-eye" />
        <span className="ai-mentor-pulse" />
      </div>
      <div>
        <p className="quest-kicker">AI Mentor</p>
        <h1 id="dashboard-title">{loadingText || `Ready, ${name}?`}</h1>
        <p>
          {nextDay
            ? `Your next mission is Day ${nextDay.day_number}: ${nextDay.topic_name}. Keep it tight, finish the lesson, then win the quiz battle.`
            : "Create a plan and AI-SAATHI will turn it into glowing daily quests."}
        </p>
        <button type="button" onClick={onCustomPlan} disabled={customPlanLoading}>
          {customPlanLoading ? "Building map..." : "Create Aptitude Quest"}
        </button>
      </div>
    </section>
  );
}

function DailyQuestCard({
  day,
  planName,
  progress,
  onContinue,
}: Readonly<{
  day: PlanDay | null;
  planName: string;
  progress: number;
  onContinue: () => void;
}>) {
  return (
    <section className="daily-quest-card" aria-label="Daily mission">
      <div>
        <p className="quest-kicker">Daily Mission</p>
        <h2>{day ? day.topic_name : "Build your first mission"}</h2>
        <p>{day ? `${day.subject} · ${day.allocated_minutes} min · Difficulty ${day.difficulty}/5` : planName}</p>
      </div>
      <div className="daily-quest-progress" aria-label={`${progress}% plan progress`}>
        <span style={{ "--value": `${progress}%` } as CSSProperties}>{progress}%</span>
      </div>
      <button type="button" onClick={onContinue} disabled={!day || day.unlocked === false}>
        Continue Quest
      </button>
    </section>
  );
}

function SkillMapPath({
  days,
  activeDay,
  onSelect,
  onStudy,
  loading,
  error,
}: Readonly<{
  days: PlanDay[];
  activeDay: PlanDay | null;
  onSelect: (day: PlanDay) => void;
  onStudy: (day: PlanDay) => void;
  loading: boolean;
  error: string;
}>) {
  if (loading) {
    return <section className="skill-map-path empty"><h2>Loading your quest map...</h2></section>;
  }

  if (!days.length) {
    return (
      <section className="skill-map-path empty">
        <p className="quest-kicker">Skill Map</p>
        <h2>Start with setup</h2>
        <p>{error || "No plan found yet."}</p>
        <Link className="quest-primary-action" href="/plan">Create Study Plan</Link>
      </section>
    );
  }

  return (
    <section className="skill-map-path" aria-label="Study plan skill map">
      <div className="skill-map-header">
        <div>
          <p className="quest-kicker">Skill Map Path</p>
          <h2>{activeDay ? `Day ${activeDay.day_number}: ${activeDay.topic_name}` : "Select a mission node"}</h2>
        </div>
        <span>{days.length} nodes</span>
      </div>
      <div className="skill-map-canvas">
        <svg viewBox="0 0 100 48" preserveAspectRatio="none" aria-hidden="true">
          <path d="M 4 36 C 15 18, 26 34, 38 22 S 55 18, 65 30 S 82 39, 96 12" />
        </svg>
        {days.slice(0, 10).map((day, index) => {
          const x = 6 + index * (88 / Math.max(1, Math.min(days.length, 10) - 1));
          const y = index % 3 === 0 ? 34 : index % 3 === 1 ? 20 : 28;
          const state = day.status === "taught" ? "complete" : day.unlocked === false ? "locked" : "ready";
          return (
            <button
              key={day.id}
              type="button"
              className={`skill-node ${state} ${activeDay?.id === day.id ? "active" : ""}`}
              style={{ left: `${x}%`, top: `${y}%` }}
              onClick={() => onSelect(day)}
              aria-label={`Day ${day.day_number}: ${day.topic_name}`}
            >
              <span>{day.day_number}</span>
            </button>
          );
        })}
      </div>
      <div className="mission-card-grid">
        {days.slice(0, 6).map((day) => (
          <PlanMissionCard
            key={day.id}
            day={day}
            selected={activeDay?.id === day.id}
            onSelect={() => onSelect(day)}
            onStudy={() => onStudy(day)}
          />
        ))}
      </div>
    </section>
  );
}

function PlanMissionCard({
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
  const locked = day.unlocked === false;
  const complete = day.status === "taught";
  return (
    <article className={`plan-mission-card ${selected ? "selected" : ""}`}>
      <button type="button" className="plan-mission-hit" onClick={onSelect}>
        <span>Day {day.day_number}</span>
        <strong>{day.topic_name}</strong>
        <small>{day.subject} · {day.allocated_minutes} min</small>
      </button>
      <div className="plan-mission-footer">
        <span className={locked ? "locked" : complete ? "complete" : "ready"}>
          {locked ? "Locked" : complete ? "Cleared" : "Ready"}
        </span>
        <button type="button" onClick={onStudy} disabled={locked}>
          {locked ? "Locked" : "Continue Quest"}
        </button>
      </div>
    </article>
  );
}

function CompactStat({ label, value, tone }: Readonly<{ label: string; value: string; tone: string }>) {
  return (
    <article className={`compact-stat ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function WeakAreaRadar({ days, weakTopic }: Readonly<{ days: PlanDay[]; weakTopic: PlanDay | null }>) {
  const topics = days.slice(0, 4);
  return (
    <section className="weak-area-radar" aria-label="Weak-area radar">
      <p className="quest-kicker">Weak-Area Radar</p>
      <h2>{weakTopic?.topic_name ?? "No weak topic yet"}</h2>
      <div className="radar-grid" aria-hidden="true">
        <span className="radar-ring ring-one" />
        <span className="radar-ring ring-two" />
        <span className="radar-axis axis-one" />
        <span className="radar-axis axis-two" />
        <span className="radar-sweep" />
      </div>
      <div className="radar-tags">
        {(topics.length ? topics : [weakTopic]).filter(Boolean).map((day, index) => (
          <span key={day?.id ?? index}>{day?.topic_name}</span>
        ))}
      </div>
    </section>
  );
}

function RevisionQueue({ days, onStudy }: Readonly<{ days: PlanDay[]; onStudy: (day: PlanDay) => void }>) {
  const queue = days.filter((day) => day.status !== "taught").slice(0, 3);
  return (
    <section className="revision-queue" aria-label="Revision queue">
      <p className="quest-kicker">Revision Queue</p>
      <h2>Next repairs</h2>
      {queue.length ? queue.map((day) => (
        <button key={day.id} type="button" onClick={() => onStudy(day)} disabled={day.unlocked === false}>
          <span>Day {day.day_number}</span>
          <strong>{day.topic_name}</strong>
        </button>
      )) : <p>All visible missions are clear.</p>}
    </section>
  );
}
