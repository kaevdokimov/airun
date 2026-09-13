const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Goal {
  id: string;
  distance: string;
  target_time_seconds: number | null;
  race_date: string;
  status: string;
  days_until_race: number;
}

export interface Activity {
  id: string;
  activity_type: string;
  distance_m: number | null;
  duration_sec: number | null;
  started_at: string;
}

export interface Recommendation {
  id: string;
  content: string;
  parsed?: {
    summary: string;
    today_recommendation: string;
    week_plan: string[];
    warnings: string[];
    progress_to_goal: string;
  };
  generated_at: string;
}

export interface WeekStats {
  total_distance_m: number;
  total_duration_sec: number;
  activity_count: number;
  activities: Activity[];
}

const TOKEN_KEY = "access_token";
const TELEGRAM_ID_KEY = "telegram_id";
const AUTH_EXPIRED_EVENT = "airun:auth-expired";
let authRedirectScheduled = false;

type ApiValidationError = { msg?: unknown; loc?: unknown };

function isApiErrorBody(value: unknown): value is { detail?: unknown } {
  return typeof value === "object" && value !== null;
}

function isApiValidationError(value: unknown): value is ApiValidationError {
  return typeof value === "object" && value !== null;
}

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getTelegramId(): number | null {
  if (typeof window === "undefined") return null;
  const stored = localStorage.getItem(TELEGRAM_ID_KEY);
  return stored ? parseInt(stored, 10) : null;
}

export function setAuth(token: string, telegramId: number) {
  authRedirectScheduled = false;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(TELEGRAM_ID_KEY, String(telegramId));
}

export function clearAuth() {
  authRedirectScheduled = false;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TELEGRAM_ID_KEY);
}

function notifySessionExpired() {
  if (typeof window === "undefined" || authRedirectScheduled) return;
  clearAuth();
  authRedirectScheduled = true;
  window.dispatchEvent(
    new CustomEvent(AUTH_EXPIRED_EVENT, {
      detail: "Сессия истекла. Сейчас вернём вас на вход.",
    }),
  );
  window.setTimeout(() => {
    window.location.href = "/";
  }, 1400);
}

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function apiFetch(path: string, options: RequestInit = {}) {
  const id = getTelegramId();
  if (!id) throw new Error("Not authenticated");
  const separator = path.includes("?") ? "&" : "?";
  const url = `${API_URL}${path}${separator}telegram_id=${id}`;
  const r = await fetch(url, { ...options, headers: { ...authHeaders(), ...options.headers } });
  if (r.status === 401) {
    notifySessionExpired();
    throw new Error("Session expired");
  }
  return r;
}

async function parseApiError(response: Response, fallback: string) {
  try {
    const data: unknown = await response.json();
    const detail = isApiErrorBody(data) ? data.detail : undefined;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .filter(isApiValidationError)
        .map((item: ApiValidationError) => {
          if (typeof item.msg !== "string") return null;
          const location = Array.isArray(item.loc)
            ? item.loc
                .filter(
                  (part: unknown): part is string | number =>
                    typeof part === "string" || typeof part === "number",
                )
                .join(".")
            : "";
          return location ? `${location}: ${item.msg}` : item.msg;
        })
        .filter((message): message is string => Boolean(message));
      if (messages.length) return messages.join("; ");
    }
  } catch {
    // Keep the original user-facing fallback when the API returns non-JSON.
  }
  return fallback;
}

export async function loginWithTelegram(authData: Record<string, string | number>) {
  const r = await fetch(`${API_URL}/api/v1/auth/telegram-web`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(authData),
  });
  if (!r.ok) throw new Error("Telegram auth failed");
  const data = await r.json();
  setAuth(data.access_token, data.telegram_id);
  return data;
}

export async function fetchGoals(): Promise<Goal[]> {
  const r = await apiFetch("/api/v1/goals");
  if (!r.ok) throw new Error(await parseApiError(r, "Не удалось загрузить цели"));
  return r.json();
}

export async function fetchWeekStats(): Promise<WeekStats | null> {
  const r = await apiFetch("/api/v1/stats/week");
  if (!r.ok) throw new Error(await parseApiError(r, "Не удалось загрузить статистику"));
  return r.json();
}

export async function fetchRecommendations(): Promise<Recommendation[]> {
  const r = await apiFetch("/api/v1/recommendations?limit=10");
  if (!r.ok) throw new Error(await parseApiError(r, "Не удалось загрузить рекомендации"));
  return r.json();
}

export { AUTH_EXPIRED_EVENT };
