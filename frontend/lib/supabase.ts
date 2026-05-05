"use client";

import { AuthError, createClient, User } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

declare global {
  var aiSaathiSupabaseClient: ReturnType<typeof createClient> | undefined;
}

if (!supabaseUrl || !supabaseKey) {
  throw new Error("Missing Supabase public environment variables.");
}

export const supabase =
  globalThis.aiSaathiSupabaseClient ??
  createClient(supabaseUrl, supabaseKey, {
    auth: {
      autoRefreshToken: true,
      detectSessionInUrl: true,
      persistSession: true,
    },
  });

globalThis.aiSaathiSupabaseClient = supabase;

export type AuthProfile = {
  userId: string;
  email: string;
  name: string;
};

export type SignUpResult = {
  profile: AuthProfile;
};

function profileFromUser(user: User): AuthProfile {
  const displayName =
    typeof user.user_metadata?.name === "string" && user.user_metadata.name.trim()
      ? user.user_metadata.name.trim()
      : typeof user.user_metadata?.full_name === "string" && user.user_metadata.full_name.trim()
        ? user.user_metadata.full_name.trim()
      : user.email?.split("@")[0] || "Learner";

  return {
    userId: user.id,
    email: user.email || "",
    name: displayName,
  };
}

function isMissingSessionError(error: AuthError | null): boolean {
  return error?.name === "AuthSessionMissingError";
}

export async function getCurrentAuthProfile(): Promise<AuthProfile | null> {
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if ((error && isMissingSessionError(error)) || !user) return null;
  if (error) throw error;
  return profileFromUser(user);
}

export async function signUpWithPassword(
  email: string,
  password: string,
  name: string
): Promise<SignUpResult> {
  const response = await fetch("/api/auth/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name }),
  });

  const payload = (await response.json().catch(() => null)) as
    | { user?: AuthProfile; error?: string }
    | null;

  if (!response.ok) {
    const message = payload?.error || "Could not create your Supabase account.";
    if (message.includes("SUPABASE_SERVICE_ROLE_KEY")) {
      throw new Error(
        "Supabase server signup is not configured. Add SUPABASE_SERVICE_ROLE_KEY to frontend/.env.local, restart the dev server, then create the account again."
      );
    }
    throw new Error(message);
  }

  if (!payload?.user) throw new Error("Supabase did not return a user for this signup.");

  await signInWithPassword(email, password);
  return { profile: payload.user };
}

export async function signInWithPassword(email: string, password: string): Promise<AuthProfile> {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  if (!data.user) throw new Error("Supabase did not return a user for this login.");
  return profileFromUser(data.user);
}

export async function signInWithGoogle(nextPath = "/dashboard"): Promise<void> {
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  const next = nextPath.startsWith("/") && !nextPath.startsWith("//") ? nextPath : "/dashboard";
  const redirectTo = origin ? `${origin}/login?next=${encodeURIComponent(next)}` : undefined;

  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo,
      queryParams: {
        access_type: "offline",
        prompt: "select_account",
      },
    },
  });

  if (error) throw error;
}

export async function completeOAuthRedirect(): Promise<AuthProfile | null> {
  if (typeof window === "undefined") return null;

  const params = new URLSearchParams(window.location.search);
  const code = params.get("code");

  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (error) throw error;
    params.delete("code");
    window.history.replaceState({}, "", `${window.location.pathname}${params.toString() ? `?${params}` : ""}`);
  }

  return getCurrentAuthProfile();
}

export async function signOutSupabase(): Promise<void> {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}
