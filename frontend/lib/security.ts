const ESCAPE_MAP: Record<string, string> = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#x27;",
  "/": "&#x2F;",
};

export function escapeHtml(str: string): string {
  return String(str).replace(/[&<>"'/]/g, (char) => ESCAPE_MAP[char] ?? char);
}

export function sanitizeInput(input: unknown): string {
  if (typeof input !== "string") {
    return "";
  }
  return input
    .trim()
    .replace(/[\x00-\x1F\x7F]/g, "")
    .slice(0, 10000);
}

export function isTrustedUrl(url: string, allowedOrigins: string[] = []): boolean {
  try {
    const parsed = new URL(url, window.location.origin);
    const allowed = new Set([
      window.location.origin,
      ...allowedOrigins,
      "https://yunwu.ai",
    ]);
    return allowed.has(parsed.origin);
  } catch (err) {
    console.warn("[security] Invalid URL in origin check:", err);
    return false;
  }
}

export function cspNonce(): string {
  if (typeof window === "undefined") {
    return "";
  }
  const nextData = window.__NEXT_DATA__ as Record<string, unknown> | undefined;
  const nonce = nextData?.nonce ?? "";
  return typeof nonce === "string" ? nonce : "";
}
