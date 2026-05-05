"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { getLearnerProfile, saveLearnerProfile } from "@/lib/api";
import { signUpWithPassword } from "@/lib/supabase";

export default function SignupPage() {
  const existingProfile = getLearnerProfile();
  const [name, setName] = useState(existingProfile.name === "Learner" ? "" : existingProfile.name);
  const [email, setEmail] = useState(existingProfile.email || "");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const trimmedName = name.trim() || "Learner";
    const trimmedEmail = email.trim().toLowerCase();

    if (!trimmedEmail || password.length < 6) {
      setError("Enter an email and a password with at least 6 characters.");
      return;
    }

    setLoading(true);
    try {
      const result = await signUpWithPassword(trimmedEmail, password, trimmedName);
      const authProfile = result.profile;

      saveLearnerProfile({
        ...existingProfile,
        userId: authProfile.userId,
        name: authProfile.name || trimmedName,
        email: authProfile.email || trimmedEmail,
      });
      window.location.href = "/dashboard";
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Could not create your study plan. Please try again."
      );
    } finally {
      setLoading(false);
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
          Continue
        </Link>
      </header>

      <div className="star-field" aria-hidden="true">
        {Array.from({ length: 28 }, (_, index) => (
          <span key={index} className={`star star-${index + 1}`} />
        ))}
      </div>

      <section className="login-stage signup-stage" aria-labelledby="signup-heading">
        <div className="assistant-row" aria-hidden="true">
          <div className="auth-robot">
            <span className="auth-robot-antenna" />
            <span className="auth-robot-head" />
            <span className="auth-robot-face" />
            <span className="auth-robot-body" />
            <span className="auth-robot-jet" />
          </div>
          <div className="speech-bubble">
            Create your account, then sign in to continue your learning run.
          </div>
        </div>

        <form className="login-card signup-card" onSubmit={handleSubmit} noValidate>
          <h1 id="signup-heading">Sign Up</h1>

          <label className="field-label" htmlFor="name">
            Your Name
          </label>
          <input
            id="name"
            name="name"
            type="text"
            autoComplete="name"
            placeholder="Aryan Sharma"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />

          <label className="field-label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            placeholder="learner@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />

          <label className="field-label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="new-password"
            placeholder="At least 6 characters"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />

          {error ? (
            <p className="error-message" role="alert">
              {error}
            </p>
          ) : null}

          <button className="login-button" type="submit" disabled={loading}>
            {loading ? "Creating account..." : "Create Account"}
          </button>

          <p className="account-copy">
            Already started? <Link href="/login">Continue learning</Link>
          </p>
        </form>
      </section>

      <div className="moon-band moon-left" aria-hidden="true" />
      <div className="moon-band moon-right" aria-hidden="true" />
    </main>
  );
}
