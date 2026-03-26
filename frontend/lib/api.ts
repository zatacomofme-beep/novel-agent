import type { ApiErrorPayload } from "@/types/api";
import { getAccessToken } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      message = payload.error.message;
    } catch {
      // Ignore JSON parse failures and fall back to generic message.
    }
    throw new Error(message);
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

  return apiFetch<T>(path, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init.headers ?? {}),
    },
  });
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
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      message = payload.error.message;
    } catch {
      // Ignore JSON parse failures and fall back to generic message.
    }
    throw new Error(message);
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
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as ApiErrorPayload;
      message = payload.error.message;
    } catch {
      // Ignore JSON parse failures and fall back to generic message.
    }
    throw new Error(message);
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
