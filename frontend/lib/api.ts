const BACKEND_BASE_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";

export const EXAMS = ["SSC CGL", "SBI PO", "IBPS PO"] as const;
export const LEVELS = ["beginner", "intermediate", "advanced"] as const;

export type ExamName = (typeof EXAMS)[number];
export type LearnerLevel = (typeof LEVELS)[number];

export interface LearnerProfile {
  userId: string;
  name: string;
  email?: string;
  picture?: string;
  exam: string;
  level: LearnerLevel;
  durationDays: number;
  userGoal?: string;
}

export interface PlanDay {
  id: string;
  plan_day_id: string;
  day_number: number;
  scheduled_date: string;
  topic_id: string;
  topic: string;
  topic_name: string;
  subject: string;
  priority: string;
  difficulty: number;
  allocated_minutes: number;
  revision_topic_ids: string[];
  status: "pending" | "taught" | string;
  taught_at?: string | null;
  best_score?: number;
  pass_mark?: number;
  unlocked?: boolean;
  unlock_reason?: string;
}

export interface StudyPlan {
  plan_id: string;
  id: string;
  user_id: string;
  exam_id: string;
  exam: string;
  level: LearnerLevel | string;
  start_date: string;
  end_date: string;
  duration: number;
  duration_days: number;
  status: string;
  created_at?: string | null;
  days: PlanDay[];
  meta?: {
    replan_flag?: boolean;
    replan_reason?: string;
    replanned_at?: string;
    [key: string]: unknown;
  };
}

export interface OnboardRequest {
  user_id: string;
  exam_id: string;
  duration_days: number;
  start_date?: string;
  name: string;
  email?: string;
  level: LearnerLevel;
  user_goal?: string;
}

export interface OnboardResponse {
  plan_id: string;
  start_date: string;
  end_date: string;
  duration_days: number;
  message: string;
}

export interface PlanResponse {
  study_plan: Omit<StudyPlan, "days">;
  study_plan_days: PlanDay[];
}

export interface TeachResponse {
  log_id: string;
  lesson_content: string;
  lesson_steps: LessonStep[];
  revision: LessonRevision | null;
  teacher_status: string;
  topic_name: string;
  status: string;
  personalization?: AdaptiveContext;
}

export interface LessonStep {
  id: string;
  title: string;
  kind: string;
  content: string;
  checkpoint?: string;
}

export interface LessonRevision {
  topic_id: string;
  topic_name: string;
  summary: string;
  quick_check: string;
}

export interface QuizQuestion {
  question_text: string;
  options: string[];
}

export interface QuizGenerateResponse {
  attempt_id: string;
  questions: QuizQuestion[];
  total: number;
  adaptive_context?: AdaptiveContext;
}

export interface QuizSubmitResponse {
  score: number;
  total: number;
  accuracy: number;
  per_question_result: boolean[];
  updated_accuracy: number;
  new_weakness_score: number;
  replan_triggered: boolean;
  top_weak_topics: WeakTopic[];
  passed: boolean;
  pass_mark: number;
  next_day_unlocked: boolean;
  recommended_action: "continue" | "revise" | string;
}

export interface TopicStat {
  topic_id: string;
  topic_name: string;
  attempts: number;
  correct: number;
  accuracy: number;
  weakness_score: number;
}

export interface WeakTopic {
  topic_id: string;
  topic_name: string;
  weakness_score: number;
  rank: number;
  recommended_extra_mins: number;
}

export interface ActivityHeatmapCell {
  date: string;
  label: string;
  attempts: number;
  questions: number;
  correct: number;
  accuracy: number;
  points: number;
  level: number;
  is_current_month: boolean;
}

export interface ActivityBadge {
  id: string;
  name: string;
  description: string;
  earned: boolean;
}

export interface ActivityProfile {
  month: string;
  heatmap: ActivityHeatmapCell[];
  points: {
    points: number;
    level: number;
    title: string;
    current_level_points: number;
    next_level_points: number;
    progress_percent: number;
  };
  streak: {
    current: number;
    best: number;
    active_days_this_month: number;
  };
  badges: ActivityBadge[];
}

export interface ProgressResponse {
  topic_stats: TopicStat[];
  top_weaknesses: WeakTopic[];
  activity?: ActivityProfile;
}

export interface ReplanResponse {
  updated_plan_id: string;
  message: string;
}

export interface SupabaseProfileResponse {
  user: {
    id: string;
    name: string;
    email?: string;
    level?: LearnerLevel | string;
    target_exam_id?: string;
    timezone?: string;
  };
  active_plan: StudyPlan | null;
  progress: ProgressResponse;
  source: "supabase" | string;
}

export interface AdaptiveContext {
  source: string;
  attempts: number;
  accuracy: number;
  weakness_score: number;
  base_difficulty: number;
  adapted_difficulty: number;
  reason: string;
  recommended_extra_mins: number;
}

export interface StudyGoal {
  name: string;
  id: string;
}

export interface AgentRequest {
  user_id: string;
  message: string;
  context?: Record<string, unknown>;
}

export interface AgentResponse {
  agent: string;
  task: string;
  message: string;
  data: Record<string, unknown>;
  events: unknown[];
}

export type AgentStreamEventName =
  | "graph_started"
  | "intent_detected"
  | "tool_started"
  | "tool_finished"
  | "node_finished"
  | "final_response"
  | "error";

export interface AgentStreamEvent {
  event: AgentStreamEventName;
  data: Record<string, unknown>;
}

const PROFILE_KEY = "aiSaathiProfile";
const SELECTED_DAY_KEY = "aiSaathiSelectedPlanDay";

function createUserId(): string {
  return `learner-${Math.random().toString(36).slice(2, 10)}`;
}

export function getLearnerProfile(): LearnerProfile {
  if (typeof window === "undefined") {
    return {
      userId: "learner-preview",
      name: "Learner",
      exam: "SSC CGL",
      level: "beginner",
      durationDays: 5,
    };
  }

  const raw = window.localStorage.getItem(PROFILE_KEY);
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as Partial<LearnerProfile>;
      if (parsed.userId) {
        return {
          userId: parsed.userId,
          name: parsed.name || "Learner",
          email: parsed.email || "",
          picture: parsed.picture || "",
          exam: parsed.exam || "SSC CGL",
          level: LEVELS.includes(parsed.level as LearnerLevel) ? (parsed.level as LearnerLevel) : "beginner",
          durationDays: parsed.durationDays || 5,
          userGoal: parsed.userGoal || "",
        };
      }
    } catch {
      // Fall through and create a fresh profile.
    }
  }

  const profile: LearnerProfile = {
    userId: createUserId(),
    name: "Learner",
    exam: "SSC CGL",
    level: "beginner",
    durationDays: 5,
  };
  saveLearnerProfile(profile);
  return profile;
}

export function saveLearnerProfile(profile: LearnerProfile): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
}

export function resetLearnerProfile(): LearnerProfile {
  const profile: LearnerProfile = {
    userId: createUserId(),
    name: "Learner",
    exam: "SSC CGL",
    level: "beginner",
    durationDays: 5,
  };
  if (typeof window !== "undefined") {
    window.sessionStorage.removeItem(SELECTED_DAY_KEY);
  }
  saveLearnerProfile(profile);
  return profile;
}

export function saveSelectedPlanDay(day: PlanDay): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(SELECTED_DAY_KEY, JSON.stringify(day));
}

export function getSelectedPlanDay(): PlanDay | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(SELECTED_DAY_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PlanDay;
  } catch {
    return null;
  }
}

export function clearSelectedPlanDay(): void {
  if (typeof window === "undefined") return;
  window.sessionStorage.removeItem(SELECTED_DAY_KEY);
}

async function fetchJson<T>(baseUrl: string, path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  const res = await fetch(`${baseUrl}${path}`, { ...options, headers });
  if (!res.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const body = (await res.json()) as { detail?: unknown; message?: string };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail
          .map((item) => {
            if (item && typeof item === "object" && "msg" in item) {
              return String((item as { msg: unknown }).msg);
            }
            return String(item);
          })
          .join(" ");
      } else if (body.message) {
        message = body.message;
      }
    } catch {
      const text = await res.text().catch(() => "");
      if (text.trim()) message = text.trim();
    }
    throw new Error(message);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  return fetchJson<T>(BACKEND_BASE_URL, path, options);
}

async function nextApiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  return fetchJson<T>("", path, options);
}

export async function healthCheck(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/health");
}

export async function listStudyGoals(): Promise<StudyGoal[]> {
  const response = await apiFetch<{ exams: Record<string, string> }>("/study/exams");
  return Object.entries(response.exams).map(([name, id]) => ({ name, id }));
}

export interface GoogleLoginProfile {
  userId: string;
  name: string;
  email: string;
  picture: string;
}

export function profileFromGoogleLogin(
  googleProfile: GoogleLoginProfile,
  current: LearnerProfile = getLearnerProfile()
): LearnerProfile {
  return {
    userId: googleProfile.userId,
    name: googleProfile.name,
    email: googleProfile.email,
    picture: googleProfile.picture,
    exam: current.exam || "SSC CGL",
    level: LEVELS.includes(current.level) ? current.level : "beginner",
    durationDays: current.durationDays || 5,
  };
}

export async function routeAfterLogin(userId: string): Promise<string> {
  try {
    await getStudyPlan(userId);
    return "/dashboard";
  } catch {
    return "/plan";
  }
}

export async function completeGoogleLogin(
  code: string,
  state: string,
  redirectUri: string
): Promise<GoogleLoginProfile> {
  return nextApiFetch<GoogleLoginProfile>("/api/auth/google/callback", {
    method: "POST",
    body: JSON.stringify({ code, state, redirectUri }),
  });
}

export async function onboardLearner(request: OnboardRequest): Promise<OnboardResponse> {
  return apiFetch<OnboardResponse>("/study/onboard", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function createCustomRagPlan(request: OnboardRequest): Promise<OnboardResponse> {
  return apiFetch<OnboardResponse>("/study/custom-plan", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getStudyPlan(userId: string): Promise<StudyPlan> {
  const response = await apiFetch<PlanResponse>(`/study/plan/${encodeURIComponent(userId)}`);
  return {
    ...response.study_plan,
    days: response.study_plan_days,
  };
}

export async function getSupabaseProfile(userId: string): Promise<SupabaseProfileResponse> {
  return apiFetch<SupabaseProfileResponse>(`/study/profile/${encodeURIComponent(userId)}`);
}

export async function teachPlanDay(planDayId: string, userId: string): Promise<TeachResponse> {
  return apiFetch<TeachResponse>(
    `/study/teach/${encodeURIComponent(planDayId)}?user_id=${encodeURIComponent(userId)}`,
    { method: "POST" }
  );
}

function parseStreamData(event: Event): Record<string, unknown> {
  return JSON.parse((event as MessageEvent).data) as Record<string, unknown>;
}

function agentStreamUrl(path: string, request: AgentRequest): string {
  const params = new URLSearchParams({
    user_id: request.user_id,
    message: request.message,
  });
  if (request.context && Object.keys(request.context).length > 0) {
    params.set("context", JSON.stringify(request.context));
  }
  return `${BACKEND_BASE_URL}${path}?${params.toString()}`;
}

export function streamStudyAgent(
  request: AgentRequest,
  onEvent: (event: AgentStreamEvent) => void,
  onFinal: (response: AgentResponse) => void,
  onError: (message: string) => void
): () => void {
  const source = new EventSource(agentStreamUrl("/study/agent/stream", request));
  const events: AgentStreamEventName[] = [
    "graph_started",
    "intent_detected",
    "tool_started",
    "tool_finished",
    "node_finished",
    "final_response",
    "error",
  ];

  events.forEach((eventName) => {
    source.addEventListener(eventName, (event) => {
      try {
        const data = parseStreamData(event);
        onEvent({ event: eventName, data });
        if (eventName === "final_response") {
          onFinal(data as unknown as AgentResponse);
          source.close();
        } else if (eventName === "error") {
          onError(String(data.message || "Study agent stream failed."));
          source.close();
        }
      } catch {
        onError("Study agent stream failed.");
        source.close();
      }
    });
  });

  source.onerror = () => {
    onError("Study agent stream failed.");
    source.close();
  };
  return () => source.close();
}

export function streamTeachPlanDay(
  planDayId: string,
  userId: string,
  onStatus: (message: string) => void,
  onComplete: (lesson: TeachResponse) => void,
  onError: (message: string) => void
): () => void {
  const source = new EventSource(
    `${BACKEND_BASE_URL}/study/teach/${encodeURIComponent(planDayId)}/stream?user_id=${encodeURIComponent(userId)}`
  );
  const statusEvents = [
    "graph_started",
    "intent_detected",
    "tool_started",
    "tool_finished",
    "node_finished",
  ];
  statusEvents.forEach((eventName) => {
    source.addEventListener(eventName, (event) => {
      const data = parseStreamData(event) as { message?: string; tool_name?: string; agent?: string };
      if (data.message) onStatus(data.message);
      else if (data.tool_name) onStatus(`Running ${data.tool_name}.`);
      else if (data.agent) onStatus(`${data.agent} is working.`);
    });
  });
  source.addEventListener("final_response", (event) => {
    const response = parseStreamData(event) as unknown as AgentResponse;
    if (response.data) {
      onComplete(response.data as unknown as TeachResponse);
      source.close();
    }
  });
  source.addEventListener("complete", (event) => {
    onComplete(parseStreamData(event) as unknown as TeachResponse);
    source.close();
  });
  source.addEventListener("error", (event) => {
    try {
      const data = parseStreamData(event) as { message?: string };
      onError(data.message || "Could not open this lesson.");
    } catch {
      onError("Could not open this lesson.");
    }
    source.close();
  });
  source.onerror = () => {
    onError("Could not open this lesson.");
    source.close();
  };
  return () => source.close();
}

export async function generateStudyQuiz(
  userId: string,
  day: PlanDay,
  numQuestions = 5
): Promise<QuizGenerateResponse> {
  return apiFetch<QuizGenerateResponse>("/study/quiz/generate", {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      topic_id: day.topic_id,
      num_questions: numQuestions,
      difficulty: Math.max(1, Math.min(5, Number(day.difficulty) || 3)),
      plan_day_id: day.id,
    }),
  });
}

export async function submitStudyQuiz(
  attemptId: string,
  userAnswers: number[],
  timeTakenSecs: number
): Promise<QuizSubmitResponse> {
  return apiFetch<QuizSubmitResponse>(`/study/quiz/${encodeURIComponent(attemptId)}/submit`, {
    method: "POST",
    body: JSON.stringify({
      user_answers: userAnswers,
      time_taken_secs: Math.max(1, Math.round(timeTakenSecs)),
    }),
  });
}

export async function getProgress(userId: string): Promise<ProgressResponse> {
  return apiFetch<ProgressResponse>(`/study/progress/${encodeURIComponent(userId)}`);
}

export async function replanStudy(userId: string): Promise<ReplanResponse> {
  return apiFetch<ReplanResponse>(`/study/replan/${encodeURIComponent(userId)}`, {
    method: "POST",
  });
}
