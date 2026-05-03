"use client";

import { createClient, User } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey =
  process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseKey) {
  throw new Error("Missing Supabase public environment variables.");
}

export const supabase = createClient(supabaseUrl, supabaseKey);

export type AuthProfile = {
  userId: string;
  email: string;
  name: string;
};

function profileFromUser(user: User): AuthProfile {
  const displayName =
    typeof user.user_metadata?.name === "string" && user.user_metadata.name.trim()
      ? user.user_metadata.name.trim()
      : user.email?.split("@")[0] || "Learner";

  return {
    userId: user.id,
    email: user.email || "",
    name: displayName,
  };
}

export async function getCurrentAuthProfile(): Promise<AuthProfile | null> {
  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  if (error || !user) return null;
  return profileFromUser(user);
}

export async function signUpWithPassword(
  email: string,
  password: string,
  name: string
): Promise<AuthProfile> {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { name },
      emailRedirectTo: typeof window === "undefined" ? undefined : `${window.location.origin}/login`,
    },
  });

  if (error) throw error;
  if (!data.user) throw new Error("Supabase did not return a user for this signup.");
  return profileFromUser(data.user);
}

export async function signInWithPassword(email: string, password: string): Promise<AuthProfile> {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  if (!data.user) throw new Error("Supabase did not return a user for this login.");
  return profileFromUser(data.user);
}

export async function signOutSupabase(): Promise<void> {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}
