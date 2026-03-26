import type { TokenResponse } from "@/types/api";

const AUTH_STORAGE_KEY = "long-novel-agent.auth";
const AUTH_COOKIE_KEY = "novel_agent_token";

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64 = (token.split(".")[1] ?? "")
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), "=");
    return JSON.parse(atob(padded)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function isTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== "number") {
    return true;
  }
  return Date.now() >= payload.exp * 1000;
}

function getTokenRemainingSeconds(token: string): number | null {
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== "number") {
    return null;
  }
  return Math.max(0, Math.floor(payload.exp - Date.now() / 1000));
}

export function saveAuthSession(session: TokenResponse): void {
  if (typeof window === "undefined") {
    return;
  }
  const maxAge = getTokenRemainingSeconds(session.access_token);
  window.localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  document.cookie = `${AUTH_COOKIE_KEY}=${session.access_token}; path=/; SameSite=lax${
    maxAge !== null ? `; max-age=${maxAge}` : ""
  }`;
}

export function loadAuthSession(): TokenResponse | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = window.localStorage.getItem(AUTH_STORAGE_KEY);
  if (!raw) {
    return null;
  }
  try {
    const session = JSON.parse(raw) as TokenResponse;
    if (isTokenExpired(session.access_token)) {
      clearAuthSession();
      return null;
    }
    return session;
  } catch {
    clearAuthSession();
    return null;
  }
}

export function clearAuthSession(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_STORAGE_KEY);
  document.cookie = `${AUTH_COOKIE_KEY}=; path=/; max-age=0`;
}

export function getAccessToken(): string | null {
  const session = loadAuthSession();
  return session?.access_token ?? null;
}
