"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import {
  completeGoogleLogin,
  getLearnerProfile,
  profileFromGoogleLogin,
  resetLearnerProfile,
  routeAfterLogin,
  saveLearnerProfile,
} from "@/lib/api";
import { getCurrentAuthProfile, signInWithPassword, signOutSupabase } from "@/lib/supabase";

export default function LoginPage() {
  const [showIntro, setShowIntro] = useState(true);
  const [profile, setProfile] = useState(() => getLearnerProfile());
  const [email, setEmail] = useState(profile.email || "");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function boot() {
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const state = params.get("state");

      if (code && state) {
        setLoading(true);
        setError("");
        try {
          const googleProfile = await completeGoogleLogin(code, state, `${window.location.origin}/login`);
          const next = profileFromGoogleLogin(googleProfile);
          saveLearnerProfile(next);
          setProfile(next);
          window.history.replaceState({}, "", "/login");
          window.location.href = await routeAfterLogin(next.userId);
          return;
        } catch (err) {
          setError(err instanceof Error ? err.message : "Google sign in could not be completed.");
        } finally {
          setLoading(false);
        }
      }

      const authProfile = await getCurrentAuthProfile();
      if (!authProfile) return;
      setProfile((current) => {
        const next = {
          ...current,
          userId: authProfile.userId,
          email: authProfile.email,
          name: authProfile.name || current.name,
        };
        saveLearnerProfile(next);
        return next;
      });
      setEmail(authProfile.email);
    }

    void boot();
  }, []);

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (!email.trim() || password.length < 6) {
      setError("Enter your Supabase email and password.");
      return;
    }

    setLoading(true);
    try {
      const authProfile = await signInWithPassword(email.trim().toLowerCase(), password);
      const next = {
        ...profile,
        userId: authProfile.userId,
        email: authProfile.email,
        name: authProfile.name || profile.name,
      };
      saveLearnerProfile(next);
      setProfile(next);
      window.location.href = await routeAfterLogin(next.userId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    const next = resetLearnerProfile();
    setProfile(next);
    window.location.href = "/signup";
  }

  async function handleSignOut() {
    setError("");
    setLoading(true);
    try {
      await signOutSupabase();
      handleReset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign out.");
      setLoading(false);
    }
  }

  return (
    <main className="login-screen">
      {showIntro ? (
        <button
          className="auth-intro"
          type="button"
          aria-label="Continue"
          onClick={() => setShowIntro(false)}
          data-sound="click"
        >
          <span>Welcome to AI-SAATHI</span>
          <strong>your study run is ready</strong>
          <small>Press anywhere to continue</small>
        </button>
      ) : null}

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
        <Link className="signup-link" href="/signup">
          Sign Up
        </Link>
      </header>

      <div className="star-field" aria-hidden="true">
        {Array.from({ length: 28 }, (_, index) => (
          <span key={index} className={`star star-${index + 1}`} />
        ))}
      </div>

      <section className="login-stage" aria-labelledby="login-heading">
        <div className="assistant-row" aria-hidden="true">
          <div className="auth-robot">
            <span className="auth-robot-antenna" />
            <span className="auth-robot-head" />
            <span className="auth-robot-face" />
            <span className="auth-robot-body" />
            <span className="auth-robot-jet" />
          </div>
          <div className="speech-bubble">Continue your current preparation or start a fresh plan.</div>
        </div>

        <form className="login-card" aria-labelledby="login-heading" onSubmit={handleLogin}>
          <h1 id="login-heading">Continue Learning</h1>

          <div className="provider-grid auth-provider-grid" aria-label="Social sign in">
            <a className="provider-button google-provider" href="/api/auth/google/start" style={{ textDecoration: "none" }}>
              <span className="google-mark" aria-hidden="true">G</span>
              Continue with Google
            </a>
          </div>

          <div className="divider">OR</div>

          <label className="field-label" htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="learner@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />

          <label className="field-label" htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            placeholder="Your password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          {error ? <p className="error-message" role="alert">{error}</p> : null}

          <button className="login-button" type="submit" disabled={loading}>
            {loading ? "Signing in..." : "Sign In"}
          </button>

          <button className="login-button" type="button" onClick={handleReset} disabled={loading} style={{ marginTop: "0.75rem" }}>
            Create New Account
          </button>

          <button className="login-button" type="button" onClick={handleSignOut} disabled={loading} style={{ marginTop: "0.75rem" }}>
            Sign Out
          </button>

          <p className="account-copy">
            New here? <Link href="/signup">Sign up</Link>
          </p>
        </form>
      </section>

      <div className="moon-band moon-left" aria-hidden="true" />
      <div className="moon-band moon-right" aria-hidden="true" />
    </main>
  );
}
