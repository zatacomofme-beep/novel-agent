import type { ApiErrorPayload } from "@/types/api";
import { getAccessToken, getRefreshToken, saveAuthSession, clearAuthSession } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

let refreshPromise: Promise<boolean> | null = null;

async function handleAuthRefresh(): Promise<boolean> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = doRefresh();
  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

async function doRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    await clearAuthSession();
    window.location.href = "/login";
    return false;
  }

  try {
    const response = await fetch(`${API_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      await clearAuthSession();
      window.location.href = "/login";
      return false;
    }

    const session = (await response.json()) as import("@/types/api").TokenResponse;
    saveAuthSession(session);
    return true;
  } catch {
    await clearAuthSession();
    window.location.href = "/login";
    return false;
  }
}

export function buildApiWebSocketUrl(
  path: string,
  query: Record<string, string | string[] | null | undefined> = {},
): string {
  const url = new URL(API_URL);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = path;
  url.search = "";

  for (const [key, rawValue] of Object.entries(query)) {
    if (Array.isArray(rawValue)) {
      for (const value of rawValue) {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.append(key, value);
        }
      }
      continue;
    }
    if (rawValue !== undefined && rawValue !== null && rawValue !== "") {
      url.searchParams.set(key, rawValue);
    }
  }

  return url.toString();
}

function extractDownloadFilename(contentDisposition: string | null): string | null {
  if (!contentDisposition) {
    return null;
  }

  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const basicMatch = contentDisposition.match(/filename=\"?([^\";]+)\"?/i);
  return basicMatch?.[1] ?? null;
}

export class ApiError extends Error {
  readonly code: string;
  readonly traceId: string;
  readonly status: number;

  constructor(message: string, code: string, traceId: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.traceId = traceId;
    this.status = status;
  }
}

function throwApiError(response: Response, payload?: ApiErrorPayload): never {
  const message = payload?.error.message ?? `Request failed with status ${response.status}`;
  const code = payload?.error.code ?? "unknown";
  const traceId =
    (payload?.error.metadata?.trace_id as string) ??
    response.headers.get("X-Trace-Id") ??
    "";
  throw new ApiError(message, code, traceId, response.status);
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let payload: ApiErrorPayload | undefined;
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      // Ignore JSON parse failures and fall back to generic message.
    }
    throwApiError(response, payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function apiFetchWithAuth<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getAccessToken();
  if (!token) {
    throw new Error("Authentication required.");
  }

  let response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  if (response.status === 401) {
    const refreshed = await handleAuthRefresh();
    if (refreshed) {
      const newToken = getAccessToken();
      response = await fetch(`${API_URL}${path}`, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${newToken}`,
          ...(init.headers ?? {}),
        },
        cache: "no-store",
      });
    }
  }

  if (!response.ok) {
    let payload: ApiErrorPayload | undefined;
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      // Ignore JSON parse failures and fall back to generic message.
    }
    throwApiError(response, payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function apiStreamWithAuth<T>(
  path: string,
  init: RequestInit = {},
  onEvent: (event: T) => void | Promise<void>,
): Promise<void> {
  const token = getAccessToken();
  if (!token) {
    throw new Error("Authentication required.");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let payload: ApiErrorPayload | undefined;
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      // Ignore JSON parse failures and fall back to generic message.
    }
    throwApiError(response, payload);
  }

  if (!response.body) {
    throw new Error("Streaming response body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    let newlineIndex = buffer.indexOf("\n");
    while (newlineIndex >= 0) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (line) {
        await onEvent(JSON.parse(line) as T);
      }
      newlineIndex = buffer.indexOf("\n");
    }

    if (done) {
      break;
    }
  }

  const tail = buffer.trim();
  if (tail) {
    await onEvent(JSON.parse(tail) as T);
  }
}

export async function downloadWithAuth(
  path: string,
  init: RequestInit = {},
): Promise<void> {
  const token = getAccessToken();
  if (!token) {
    throw new Error("Authentication required.");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let payload: ApiErrorPayload | undefined;
    try {
      payload = (await response.json()) as ApiErrorPayload;
    } catch {
      // Ignore JSON parse failures and fall back to generic message.
    }
    throwApiError(response, payload);
  }

  const blob = await response.blob();
  const filename =
    extractDownloadFilename(response.headers.get("content-disposition")) ??
    "export.txt";
  const objectUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(objectUrl);
}

export interface WorldBuildingSessionData {
  id: string;
  project_id: string;
  user_id: string;
  current_step: number;
  last_active_step: number;
  session_data: Record<string, unknown>;
  status: string;
  completed_steps: number[];
}

export interface WorldBuildingStartResponse {
  session: WorldBuildingSessionData;
  first_question: string;
  step: number;
  step_title: string;
}

export interface WorldBuildingStepResponse {
  step: number;
  step_title: string;
  model_summary: string;
  model_expansion: string;
  is_awaiting_follow_up: boolean;
  suggested_next_step: number;
  can_skip: boolean;
  is_complete: boolean;
  generation_failed: boolean;
}

export async function startWorldBuildingSession(
  projectId: string,
  initialIdea?: string,
): Promise<WorldBuildingStartResponse> {
  return apiFetchWithAuth<WorldBuildingStartResponse>(
    `/api/v1/projects/${projectId}/world-building/sessions`,
    {
      method: "POST",
      body: JSON.stringify({ initial_idea: initialIdea ?? "" }),
    },
  );
}

export async function getActiveWorldBuildingSession(
  projectId: string,
): Promise<WorldBuildingSessionData | null> {
  return apiFetchWithAuth<WorldBuildingSessionData | null>(
    `/api/v1/projects/${projectId}/world-building/sessions`,
  );
}

export async function processWorldBuildingStep(
  projectId: string,
  sessionId: string,
  userInput: string,
  skipToNext = false,
): Promise<WorldBuildingStepResponse> {
  return apiFetchWithAuth<WorldBuildingStepResponse>(
    `/api/v1/projects/${projectId}/world-building/sessions/${sessionId}/steps`,
    {
      method: "POST",
      body: JSON.stringify({ user_input: userInput, skip_to_next: skipToNext }),
    },
  );
}

