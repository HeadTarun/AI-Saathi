"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityHeatmapCell,
  getLearnerProfile,
  getProgress,
  getStudyPlan,
  getSupabaseProfile,
  LEVELS,
  LearnerProfile,
  ProgressResponse,
  replanStudy,
  saveLearnerProfile,
  StudyPlan,
} from "@/lib/api";
import { getCurrentAuthProfile } from "@/lib/supabase";

function monthFallback(): ActivityHeatmapCell[] {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return Array.from({ length: end.getDate() }, (_, index) => {
    const day = new Date(start.getFullYear(), start.getMonth(), index + 1);
    return {
      date: day.toISOString().slice(0, 10),
      label: day.toLocaleDateString(undefined, { month: "short", day: "numeric" }),
      attempts: 0,
      questions: 0,
      correct: 0,
      accuracy: 0,
      points: 0,
      level: 0,
      is_current_month: true,
    };
  });
}

function cellPosition(dateValue: string) {
  const date = new Date(`${dateValue}T00:00:00`);
  const monthStart = new Date(date.getFullYear(), date.getMonth(), 1);
  const offset = monthStart.getDay() + date.getDate() - 1;
  return {
    gridColumn: Math.floor(offset / 7) + 1,
    gridRow: (offset % 7) + 1,
  };
}

export default function ProfilePage() {
  const [progress, setProgress] = useState<ProgressResponse | null>(null);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [selectedCell, setSelectedCell] = useState<ActivityHeatmapCell | null>(null);
  const [loading, setLoading] = useState(true);
  const [replanning, setReplanning] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const initialProfile = useMemo(() => getLearnerProfile(), []);
  const [profile, setProfile] = useState<LearnerProfile>(initialProfile);
  const profileRef = useRef(initialProfile);
  const cells = useMemo(() => progress?.activity?.heatmap?.length ? progress.activity.heatmap : monthFallback(), [progress]);
  const totalAttempts = progress?.topic_stats.reduce((sum, topic) => sum + topic.attempts, 0) ?? 0;
  const totalCorrect = progress?.topic_stats.reduce((sum, topic) => sum + topic.correct, 0) ?? 0;
  const averageAccuracy = totalAttempts ? Math.round((totalCorrect / totalAttempts) * 100) : 0;
  const taught = plan?.days.filter((day) => day.status === "taught").length ?? 0;
  const activity = progress?.activity;
  const pointState = activity?.points ?? {
    points: totalCorrect * 10 + Math.max(0, totalAttempts - totalCorrect) * 2,
    level: 1,
    title: "Rookie",
    current_level_points: 0,
    next_level_points: 120,
    progress_percent: 0,
  };
  const monthLabel = activity?.month ?? new Date().toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const earnedBadges = activity?.badges.filter((badge) => badge.earned).length ?? 0;

  const loadProfile = useCallback(async () => {
    const currentProfile = profileRef.current;
    setLoading(true);
    setError("");
    try {
      const authProfile = await getCurrentAuthProfile();
      const googleUserId = !authProfile && currentProfile.userId.startsWith("google-") ? currentProfile.userId : "";

      if (!authProfile && !googleUserId) {
        window.location.href = "/login?next=/profile";
        return;
      }

      const userId = authProfile?.userId || googleUserId;
      const [profileData, progressData, planData] = await Promise.all([
        getSupabaseProfile(userId).catch(() => null),
        getProgress(userId),
        getStudyPlan(userId).catch(() => null),
      ]);
      if (profileData?.user) {
        const nextProfile: LearnerProfile = {
          ...currentProfile,
          userId: profileData.user.id,
          name: profileData.user.name || authProfile?.name || currentProfile.name,
          email: profileData.user.email || authProfile?.email || currentProfile.email,
          level: LEVELS.includes(profileData.user.level as LearnerProfile["level"])
            ? (profileData.user.level as LearnerProfile["level"])
            : currentProfile.level,
          exam: profileData.active_plan?.exam || profileData.active_plan?.exam_id || currentProfile.exam,
          durationDays: profileData.active_plan?.duration_days || currentProfile.durationDays,
        };
        profileRef.current = nextProfile;
        saveLearnerProfile(nextProfile);
        setProfile(nextProfile);
      }
      setProgress(progressData);
      setPlan(planData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your progress yet.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void loadProfile();
    }, 0);
    return () => window.clearTimeout(id);
  }, [loadProfile]);

  async function handleReplan() {
    setReplanning(true);
    setMessage("");
    setError("");
    try {
      const result = await replanStudy(profile.userId);
      setMessage(result.message.replace(/^Plan created:\s*/i, "Plan updated: "));
      await loadProfile();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not adjust your plan.");
    } finally {
      setReplanning(false);
    }
  }

  return (
    <main className="heatmap-page">
      <header className="heatmap-nav" aria-label="Profile navigation">
        <Link className="brand" href="/" aria-label="AI-SAATHI home">
          <span className="brand-coin" aria-hidden="true" />
          <span>AI-SAATHI</span>
        </Link>
        <nav className="heatmap-links" aria-label="Primary">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/study">Study</Link>
          <Link href="/profile">Profile</Link>
        </nav>
        <Link className="lp-btn-signup" href="/signup" data-sound="click">New Plan</Link>
      </header>

      <section className="heatmap-hero" aria-labelledby="profile-title">
        <p className="lp-kicker">Learner Profile</p>
        <h1 id="profile-title">{profile.name}</h1>
        <p>
          {profile.exam} preparation powered by Supabase quiz history, activity, XP, levels, and badges.
        </p>
      </section>

      <section className="heatmap-shell" aria-label="Profile summary">
        <div className="profile-player-card">
          <div className="profile-avatar" aria-hidden="true">
            {profile.name.slice(0, 1).toUpperCase()}
          </div>
          <div className="profile-player-main">
            <p className="section-kicker">Supabase Player Card</p>
            <h2>Level {pointState.level} {pointState.title}</h2>
            <p>{pointState.points} XP earned from saved quiz attempts.</p>
            <span className="progress-track profile-xp-track">
              <span style={{ width: `${Math.max(4, Math.min(100, pointState.progress_percent))}%` }} />
            </span>
            <span className="profile-xp-copy">
              {pointState.next_level_points - pointState.points} XP to Level {pointState.level + 1}
            </span>
          </div>
        </div>

        <div className="heatmap-summary" aria-label="Profile stats">
          <span>
            <strong>{pointState.points}</strong>
            XP points
          </span>
          <span>
            <strong>{activity?.streak.current ?? 0}</strong>
            Current streak
          </span>
          <span>
            <strong>{earnedBadges}/{activity?.badges.length ?? 0}</strong>
            Badges earned
          </span>
          <span>
            <strong>{averageAccuracy}%</strong>
            Accuracy
          </span>
        </div>

        {loading ? (
          <p style={{ color: "#f7fbff", textAlign: "center" }}>Loading your profile...</p>
        ) : (
          <>
            <div className="heatmap-title-row">
              <div>
                <p className="section-kicker">Monthly Activity</p>
                <h2>{monthLabel}</h2>
              </div>
              <div className="profile-mini-stats" aria-label="Monthly activity stats">
                <span>{activity?.streak.active_days_this_month ?? 0} active days</span>
                <span>Best streak {activity?.streak.best ?? 0}</span>
              </div>
            </div>
            <div className="heatmap-board">
              <div className="heatmap-days" aria-hidden="true">
                <span>Sun</span>
                <span>Mon</span>
                <span>Tue</span>
                <span>Wed</span>
                <span>Thu</span>
                <span>Fri</span>
                <span>Sat</span>
              </div>
              <div className="heatmap-grid" style={{ gridTemplateColumns: `repeat(${Math.max(5, Math.ceil((cells.length + new Date(`${cells[0]?.date ?? ""}T00:00:00`).getDay()) / 7))}, 16px)` }}>
                {cells.map((cell, index) => (
                  <button
                    key={`${cell.date}-${index}`}
                    className="heatmap-cell"
                    type="button"
                    data-level={cell.level}
                    data-tooltip={`${cell.points} XP, ${cell.questions} questions on ${cell.label}`}
                    aria-label={`${cell.points} XP, ${cell.questions} questions on ${cell.label}`}
                    style={cellPosition(cell.date)}
                    onClick={() => setSelectedCell(cell)}
                    data-sound="click"
                  />
                ))}
              </div>
            </div>

            <div className="heatmap-footer-row">
              <div className="heatmap-selected" aria-live="polite">
                {selectedCell
                  ? `${selectedCell.label}: ${selectedCell.points} XP, ${selectedCell.correct}/${selectedCell.questions} correct, ${Math.round(selectedCell.accuracy)}% accuracy.`
                  : "Tap a square to inspect Supabase activity."}
              </div>
              <div className="heatmap-legend" aria-label="Activity legend">
                <span>Less</span>
                {[0, 1, 2, 3, 4].map((level) => (
                  <span key={level} className="heatmap-legend-cell" data-level={level} />
                ))}
                <span>More</span>
              </div>
            </div>
          </>
        )}
      </section>

      {activity?.badges.length ? (
        <section className="profile-badge-section" aria-labelledby="badges-heading">
          <div className="section-heading-row">
            <div>
              <p className="section-kicker">Achievements</p>
              <h2 id="badges-heading">Badges</h2>
              <p>Earned from quiz attempts, accuracy, streaks, and topic progress saved in Supabase.</p>
            </div>
          </div>
          <div className="profile-badge-grid">
            {activity.badges.map((badge) => (
              <article className={`profile-badge-card ${badge.earned ? "earned" : ""}`} key={badge.id}>
                <span className="profile-badge-medal" aria-hidden="true">{badge.earned ? "*" : "-"}</span>
                <h3>{badge.name}</h3>
                <p>{badge.description}</p>
                <span>{badge.earned ? "Unlocked" : "Locked"}</span>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="track-section" aria-labelledby="progress-heading">
        <div className="section-kicker">Progress</div>
        <div className="section-heading-row">
          <div>
            <h2 id="progress-heading">Topic Performance</h2>
            <p>Review accuracy, attempts, lessons opened ({taught}), and topics that deserve more practice time.</p>
          </div>
          <button className="roadmap-button" type="button" onClick={handleReplan} disabled={replanning || !plan}>
            {replanning ? "Adjusting..." : "Adjust Plan"}
          </button>
        </div>

        {message ? <p role="status" style={{ color: "#85f7b0", fontWeight: 900 }}>{message}</p> : null}
        {error ? <p role="alert" style={{ color: "#ffb4b4", fontWeight: 900 }}>{error}</p> : null}

        {progress && progress.topic_stats.length > 0 ? (
          <div className="track-grid">
            {progress.topic_stats.map((topic) => (
              <article className="track-card" key={topic.topic_id}>
                <span className={`track-art ${topic.accuracy >= 70 ? "python" : topic.accuracy >= 40 ? "data" : "ai"}`} aria-hidden="true">
                  <span className="art-sky" />
                  <span className="art-land" />
                  <span className="art-marker" />
                </span>
                <span className="track-meta">
                  <span>{topic.attempts} attempts</span>
                  <span className={`difficulty ${topic.accuracy >= 70 ? "beginner" : "advanced"}`}>{Math.round(topic.accuracy)}%</span>
                </span>
                <span className="track-title">{topic.topic_name}</span>
                <span className="track-description">{topic.correct} correct answers · focus score {Math.round(topic.weakness_score)}</span>
                <span className="progress-row">
                  <span>{Math.round(topic.accuracy)}% accuracy</span>
                  <span>{topic.correct}/{topic.attempts}</span>
                </span>
                <span className="progress-track">
                  <span style={{ width: `${Math.max(4, topic.accuracy)}%` }} />
                </span>
                <span className="badge-chip">{topic.weakness_score >= 60 ? "Extra practice" : "Steady progress"}</span>
              </article>
            ))}
          </div>
        ) : (
          <div className="roadmap-panel" style={{ maxWidth: 720, margin: "0 auto" }}>
            <h3>No quiz results yet</h3>
            <p>Complete one quiz battle to unlock topic progress and focus areas.</p>
            <Link className="roadmap-button" href="/dashboard">Open Dashboard</Link>
          </div>
        )}

        {progress && progress.top_weaknesses.length > 0 ? (
          <aside className="roadmap-panel" style={{ marginTop: "2rem" }} aria-label="Focus areas">
            <p className="section-kicker">Focus Areas</p>
            <h3>Recommended Revision</h3>
            <ol>
              {progress.top_weaknesses.slice(0, 5).map((topic) => (
                <li key={topic.topic_id}>
                  <span>{topic.rank}</span>
                  {topic.topic_name} · {Math.round(topic.weakness_score)} focus score
                </li>
              ))}
            </ol>
          </aside>
        ) : null}
      </section>
    </main>
  );
}
