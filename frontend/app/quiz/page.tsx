import Link from "next/link";

export default function QuizPage() {
  return (
    <main className="quest-world quiz-lobby">
      <header className="quest-nav" aria-label="Quiz navigation">
        <Link className="quest-brand" href="/">
          <span className="quest-brand-mark">A</span>
          <span>AI-SAATHI</span>
        </Link>
        <nav aria-label="Primary">
          <Link href="/dashboard">Quest Map</Link>
          <Link href="/plan">Plan</Link>
          <Link href="/study">Arena</Link>
          <Link className="active" href="/quiz">Quiz</Link>
          <Link href="/profile">Profile</Link>
        </nav>
        <Link className="quest-primary-action" href="/study">
          Start Battle
        </Link>
      </header>

      <section className="quiz-lobby-stage" aria-labelledby="quiz-lobby-title">
        <div className="quiz-lobby-card">
          <p className="quest-kicker">Boss Quiz Lobby</p>
          <h1 id="quiz-lobby-title">Enter the Study Arena to unlock your next quiz battle.</h1>
          <p>
            Quizzes are generated from your active mission, weak-topic memory, and Supabase progress, so the battle starts inside the arena after the lesson card.
          </p>
          <div className="quiz-lobby-actions">
            <Link className="quest-primary-action" href="/study">Open Arena</Link>
            <Link className="quest-secondary-action" href="/dashboard">View Quest Map</Link>
          </div>
        </div>
      </section>
    </main>
  );
}
