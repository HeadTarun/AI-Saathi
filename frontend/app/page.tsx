"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

const stars = [
  { w: 7, h: 7, l: "6%", t: "8%" },
  { w: 7, h: 7, l: "17%", t: "28%" },
  { w: 10, h: 10, l: "27%", t: "13%" },
  { w: 7, h: 7, l: "39%", t: "22%" },
  { w: 7, h: 7, l: "53%", t: "44%" },
  { w: 10, h: 10, l: "66%", t: "18%" },
  { w: 7, h: 7, l: "78%", t: "36%" },
  { w: 7, h: 7, l: "88%", t: "14%" },
  { w: 7, h: 7, l: "4%", t: "56%" },
  { w: 7, h: 7, l: "23%", t: "64%" },
  { w: 10, h: 10, l: "48%", t: "70%" },
  { w: 7, h: 7, l: "82%", t: "60%" },
];

const ctaBandStars = [
  { w: 7, h: 7, l: "8%", t: "20%" },
  { w: 10, h: 10, l: "32%", t: "15%" },
  { w: 7, h: 7, l: "58%", t: "30%" },
  { w: 7, h: 7, l: "78%", t: "18%" },
  { w: 7, h: 7, l: "92%", t: "40%" },
];

const tickerItems = [
  "Smart Lessons", "Adaptive Quizzes", "Instant Feedback", "XP Rewards",
  "Streak Battles", "Skill Badges", "Focus Areas", "Study Plans", "Level Ups", "AI Guidance",
  "Smart Lessons", "Adaptive Quizzes", "Instant Feedback", "XP Rewards",
  "Streak Battles", "Skill Badges", "Focus Areas", "Study Plans", "Level Ups", "AI Guidance",
];

const tracks = [
  { cls: "lp-trk-python", label: "Concept Arena", title: "Ratio & Proportion Sprint", xp: "1,240 XP" },
  { cls: "lp-trk-data", label: "Data Track", title: "Data Analyst Challenge", xp: "860 XP" },
  { cls: "lp-trk-web", label: "Code Track", title: "Python Basics League", xp: "1,710 XP" },
  { cls: "lp-trk-ai", label: "AI Track", title: "ML Engineer Quest", xp: "430 XP" },
];

const codexTabs = [
  {
    id: "system",
    label: "Overview",
    title: "A Learning Platform That Feels Like a Game",
    subtitle: "AI-SAATHI helps learners study, compete, improve, and see progress every time they answer.",
    bullets: [
      "Learners start with an exam target and receive a short study plan.",
      "Every lesson can turn into a quiz battle with points, streaks, and badge rewards.",
      "The platform remembers progress so the next challenge can match the learner better.",
      "Profile insights connect daily learning to focus areas and next practice steps.",
      "The experience is built for demos, classrooms, coaching centers, and self-paced learners.",
    ],
  },
  {
    id: "learning",
    label: "Learning",
    title: "Personalized Lessons Without Overload",
    subtitle: "The learner sees simple explanations, examples, and next steps while the complex work stays invisible.",
    bullets: [
      "Lessons include simple explanations, key points, real-world examples, and common mistakes.",
      "Difficulty can start at beginner, intermediate, or advanced.",
      "The app keeps the learner focused on one topic at a time.",
      "Each study session naturally leads into a quiz, so learning becomes active.",
      "Feedback is designed to feel encouraging and actionable.",
    ],
  },
  {
    id: "flow",
    label: "Journey",
    title: "The AI-SAATHI Learning Journey",
    subtitle: "A simple loop keeps the experience clear for students and compelling for clients.",
    bullets: [
      "Choose a topic and level.",
      "Learn through a focused guided lesson.",
      "Take a quiz battle based on that lesson.",
      "Receive instant feedback, weak-area guidance, XP, streak updates, and badges.",
      "Use your profile to decide what needs revision next.",
    ],
  },
  {
    id: "rewards",
    label: "Rewards",
    title: "XP, Streaks, Levels, and Badges",
    subtitle: "Every correct answer becomes a visible win, making progress feel immediate.",
    bullets: [
      "Correct answers earn XP.",
      "Longer streaks unlock bonus rewards.",
      "Levels help learners see how far they have grown.",
      "Badges celebrate milestones like first lesson, perfect quiz, and topic mastery.",
      "The reward system stays simple enough for learners to understand instantly.",
    ],
  },
  {
    id: "support",
    label: "Support",
    title: "Built to Keep Learners Moving",
    subtitle: "AI-SAATHI is designed to guide students forward even when they struggle.",
    bullets: [
      "If a learner gets stuck, feedback explains what went wrong.",
      "Weak areas are surfaced after evaluation.",
      "Improvement tips make the next action clear.",
      "Profile insights turn learning into a goal-oriented plan.",
      "The product experience stays stable and demo-friendly.",
    ],
  },
];

const endpoints = [
  {
    path: "Dashboard",
    purpose: "The learner follows a daily study plan and opens lessons from one place.",
    request: ["Target exam", "Current level", "Study duration"],
    response: ["Daily plan", "Topic cards", "Lesson actions", "Quiz actions", "Plan progress"],
  },
  {
    path: "Quiz",
    purpose: "The lesson turns into a short challenge that tests understanding.",
    request: ["Plan day", "Topic", "Difficulty"],
    response: ["Questions", "Answer options", "Score", "Accuracy", "Revision focus"],
  },
  {
    path: "Evaluate",
    purpose: "The learner receives feedback, rewards, and a clear next step.",
    request: ["Selected answers", "Quiz battle"],
    response: ["Score", "Accuracy", "Focus areas", "Plan adjustment hint", "Next step"],
  },
  {
    path: "Profile",
    purpose: "The learner reviews progress, focus areas, and study activity.",
    request: ["Study history", "Quiz results", "Active plan"],
    response: ["Topic accuracy", "Activity map", "Focus areas", "Plan adjustment", "Profile summary"],
  },
];

const arenaStats = [
  { label: "Study Modes", value: "4" },
  { label: "Journey Steps", value: "5" },
  { label: "Max Level", value: "10" },
  { label: "Reward Types", value: "4" },
];

export default function LandingPage() {
  const [activeTab, setActiveTab] = useState(codexTabs[0].id);
  const [activeEndpoint, setActiveEndpoint] = useState(endpoints[0].path);
  const [isDayMode, setIsDayMode] = useState(false);

  const currentTab = useMemo(
    () => codexTabs.find((tab) => tab.id === activeTab) ?? codexTabs[0],
    [activeTab]
  );
  const currentEndpoint = useMemo(
    () => endpoints.find((endpoint) => endpoint.path === activeEndpoint) ?? endpoints[0],
    [activeEndpoint]
  );

  return (
    <main className={`lp-root ${isDayMode ? "lp-day" : "lp-night"}`}>
      {/* NAV */}
      <nav className="lp-topnav">
        <Link className="brand" href="/" aria-label="AI-SAATHI home">
          <span className="brand-coin" aria-hidden="true" />
          <span>AI-SAATHI</span>
        </Link>
        <div className="lp-nav-links">
          <a href="#lp-features">Features</a>
          <a href="#lp-about">How it works</a>
          <a href="#lp-codex">Experience</a>
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/profile">Profile</Link>
          <Link href="/login">Continue</Link>
        </div>
        <div className="lp-nav-actions">
          <button
            className="lp-daynight"
            type="button"
            aria-pressed={isDayMode}
            aria-label={isDayMode ? "Switch to night mode" : "Switch to day mode"}
            onClick={() => setIsDayMode((mode) => !mode)}
            data-sound="click"
          >
            <span className="lp-daynight-icon" aria-hidden="true" />
            <span>{isDayMode ? "Day" : "Night"}</span>
          </button>
          <Link className="lp-btn-signup" href="/signup" data-sound="click">Start</Link>
        </div>
      </nav>

      {/* HERO */}
      <section className="lp-hero">
        <div className="lp-hero-bg-life" aria-hidden="true">
          <span className="lp-life-pixel lp-life-1" />
          <span className="lp-life-pixel lp-life-2" />
          <span className="lp-life-pixel lp-life-3" />
          <span className="lp-life-pixel lp-life-4" />
          <span className="lp-life-pixel lp-life-5" />
          <span className="lp-life-pixel lp-life-6" />
          <span className="lp-life-pixel lp-life-7" />
          <span className="lp-life-pixel lp-life-8" />
          <span className="lp-air-cloud lp-air-cloud-1" />
          <span className="lp-air-cloud lp-air-cloud-2" />
          <span className="lp-air-cloud lp-air-cloud-3" />
          <span className="lp-air-flower lp-air-flower-1" />
          <span className="lp-air-flower lp-air-flower-2" />
          <span className="lp-air-flower lp-air-flower-3" />
          <span className="lp-air-flower lp-air-flower-4" />
          <span className="lp-air-flower lp-air-flower-5" />
          <span className="lp-life-scan" />
        </div>
        <div className="lp-stars" aria-hidden="true">
          {stars.map((s, i) => (
            <span key={i} className="lp-star" style={{ width: s.w, height: s.h, left: s.l, top: s.t }} />
          ))}
        </div>

        {/* World art */}
        <div className="lp-world-art" aria-hidden="true">
          <div className="lp-sky-grid" />
          <div className="lp-w-sun" />
          <div className="lp-w-ring" />
          <div className="lp-w-cloud lp-cloud-a" />
          <div className="lp-w-cloud lp-cloud-b" />
          <div className="lp-w-island">
            <span className="lp-w-tower" />
            <span className="lp-w-tree lp-w-tree-a" />
            <span className="lp-w-tree lp-w-tree-b" />
          </div>
          <div className="lp-w-float">
            <span className="lp-w-gem" />
            <span className="lp-w-fbase" />
          </div>
        </div>

        <div className="lp-hero-copy">
          <div className="lp-eyebrow">Compete, learn, level up</div>
          <h1 className="lp-hero-h1">AI-SAATHI</h1>
          <p className="lp-hero-sub">
            A gamified competitive learning platform with study plans, guided lessons, adaptive quizzes, instant feedback, XP, streaks, and profile insights.
          </p>
          <div className="lp-cta-row">
            <Link className="lp-btn-cta-p" href="/signup" data-sound="click">Get Started -&gt;</Link>
          </div>

          <div className="lp-arena-stats" aria-label="AI-SAATHI platform stats">
            {arenaStats.map((stat) => (
              <span key={stat.label}>
                <strong>{stat.value}</strong>
                {stat.label}
              </span>
            ))}
          </div>

          <div className="lp-mascot-row" aria-hidden="true">
            <div className="pixel-computer lp-pixel-pc">
              <span className="monitor" />
              <span className="face" />
              <span className="base" />
            </div>
            <div className="lp-bubble">Ready to enter the arena?</div>
          </div>
        </div>
      </section>

      {/* TICKER */}
      <div className="lp-ticker-wrap" aria-hidden="true">
        <div className="lp-ticker-inner">
          {tickerItems.map((item, i) => (
            <span key={i} className="lp-t-item">
              <span className="lp-t-dot" />
              {item}
            </span>
          ))}
        </div>
      </div>

      {/* FEATURES */}
      <section className="lp-section" id="lp-features">
        <div className="lp-kicker">Why AI-SAATHI?</div>
        <h2 className="lp-sec-h">Everything you need to learn, compete, and improve</h2>
        <div className="lp-feat-grid">
          <div className="lp-feat-card lp-feat-blue">
            <div className="lp-feat-icon">AI</div>
            <h3>Smart Lessons</h3>
            <p>Enter any topic and AI-SAATHI creates a focused lesson for your current level.</p>
          </div>
          <div className="lp-feat-card lp-feat-yellow">
            <div className="lp-feat-icon">XP</div>
            <h3>Competitive Progress</h3>
            <p>XP, streaks, levels, and badges turn every correct answer into visible progress.</p>
          </div>
          <div className="lp-feat-card lp-feat-red">
            <div className="lp-feat-icon">!</div>
            <h3>Weak Area Detection</h3>
            <p>Every evaluation returns feedback, explanations, weak areas, and an improvement tip for the next round.</p>
          </div>
          <div className="lp-feat-card lp-feat-teal">
            <div className="lp-feat-icon">10</div>
            <h3>Adaptive Difficulty</h3>
            <p>The platform tracks your session and nudges the challenge up or down based on recent quiz results.</p>
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="lp-section lp-how-section" id="lp-about">
        <div className="lp-kicker">How it works</div>
        <h2 className="lp-sec-h">Three steps in every learning battle</h2>
        <div className="lp-steps-row">
          <div className="lp-step-card">
            <div className="lp-step-num">01</div>
            <h3>Plan</h3>
            <p>Choose an exam target and level. AI-SAATHI creates a short study run with daily topics.</p>
          </div>
          <div className="lp-step-arrow" aria-hidden="true">-&gt;</div>
          <div className="lp-step-card">
            <div className="lp-step-num">02</div>
            <h3>Quiz</h3>
            <p>Face an AI-generated question from your current topic and submit your answer.</p>
          </div>
          <div className="lp-step-arrow" aria-hidden="true">-&gt;</div>
          <div className="lp-step-card">
            <div className="lp-step-num">03</div>
            <h3>Evaluate</h3>
            <p>Get feedback, accuracy, focus areas, and your next learning move.</p>
          </div>
        </div>
      </section>

      {/* SYSTEM CODEX */}
      <section className="lp-section lp-codex-section" id="lp-codex">
        <div className="lp-kicker">Client Experience</div>
        <h2 className="lp-sec-h">A simple story clients can understand in seconds</h2>
        <div className="lp-codex-layout">
            <div className="lp-codex-tabs" role="tablist" aria-label="AI-SAATHI experience sections">
            {codexTabs.map((tab) => (
              <button
                key={tab.id}
                className={`lp-codex-tab ${activeTab === tab.id ? "active" : ""}`}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.id}
                onClick={() => setActiveTab(tab.id)}
                data-sound="click"
              >
                {tab.label}
              </button>
            ))}
          </div>

          <article className="lp-codex-panel">
            <div className="lp-codex-header">
              <span className="lp-block-icon" aria-hidden="true" />
              <div>
                <p className="lp-kicker">Experience Card</p>
                <h3>{currentTab.title}</h3>
                <p>{currentTab.subtitle}</p>
              </div>
            </div>
            <ul className="lp-codex-list">
              {currentTab.bullets.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </article>
        </div>

        <div className="lp-endpoint-console" aria-label="Learning journey content">
          <div>
            <p className="lp-kicker">Learning Journey</p>
            <h3>Choose a learner moment</h3>
            <div className="lp-endpoint-buttons">
              {endpoints.map((endpoint) => (
                <button
                  key={endpoint.path}
                  className={`lp-endpoint-button ${activeEndpoint === endpoint.path ? "active" : ""}`}
                  type="button"
                  onClick={() => setActiveEndpoint(endpoint.path)}
                  data-sound="click"
                >
                  {endpoint.path}
                </button>
              ))}
            </div>
          </div>
          <div className="lp-endpoint-panel">
            <span className="lp-endpoint-path">{currentEndpoint.path}</span>
            <p>{currentEndpoint.purpose}</p>
            <div className="lp-endpoint-grid">
              <div>
                <strong>You choose</strong>
                <ul>
                  {currentEndpoint.request.map((field) => (
                    <li key={field}>{field}</li>
                  ))}
                </ul>
              </div>
              <div>
                <strong>You see</strong>
                <ul>
                  {currentEndpoint.response.map((field) => (
                    <li key={field}>{field}</li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* TRACKS PREVIEW */}
      <section className="lp-section">
        <div className="lp-kicker">Competitive Tracks</div>
        <h2 className="lp-sec-h">Choose your next challenge</h2>
        <div className="lp-prev-grid">
          {tracks.map((trk) => (
            <Link key={trk.cls} className={`lp-prev-track ${trk.cls}`} href="/dashboard">
              <span className="lp-trk-art">
                <span className="lp-art-sky" />
                <span className="lp-art-land" />
                <span className="lp-art-marker" />
              </span>
              <span className="lp-prev-label">{trk.label}</span>
              <span className="lp-prev-title">{trk.title}</span>
              <span className="lp-prev-xp">{trk.xp}</span>
            </Link>
          ))}
        </div>
        <div className="lp-center-cta">
          <Link className="lp-btn-cta-p" href="/dashboard" data-sound="click">Browse challenges -&gt;</Link>
        </div>
      </section>

      {/* CTA BAND */}
      <section className="lp-cta-band">
        <div className="lp-stars" aria-hidden="true">
          {ctaBandStars.map((s, i) => (
            <span key={i} className="lp-star" style={{ width: s.w, height: s.h, left: s.l, top: s.t }} />
          ))}
        </div>
        <div className="lp-cta-inner">
          <div className="pixel-computer lp-pixel-pc lp-cta-pc" aria-hidden="true">
            <span className="monitor" />
            <span className="face" />
            <span className="base" />
          </div>
          <div>
            <h2>Start your AI-SAATHI run today</h2>
            <p>Build a plan, open a lesson, take a quiz, earn XP, and track your progress.</p>
            <div className="lp-cta-row">
              <Link className="lp-btn-cta-p" href="/signup" data-sound="click">Create study plan -&gt;</Link>
              <Link className="lp-btn-cta-s" href="/login" data-sound="click">Continue learning</Link>
            </div>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="lp-footer">
        <div className="lp-foot-brand">
          <Link className="brand" href="/" aria-label="AI-SAATHI home">
            <span className="brand-coin" aria-hidden="true" />
            <span>AI-SAATHI</span>
          </Link>
          <p>Your gamified AI learning companion.</p>
        </div>
        <div className="lp-foot-links">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/study">Study</Link>
          <Link href="/profile">Profile</Link>
          <Link href="/login">Continue</Link>
          <Link href="/signup">Start</Link>
        </div>
        <div className="lp-foot-copy">Copyright 2026 AI-SAATHI. All rights reserved.</div>
      </footer>

      <div className="moon-band moon-left" aria-hidden="true" />
      <div className="moon-band moon-right" aria-hidden="true" />
    </main>
  );
}
