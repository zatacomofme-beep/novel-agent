// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  clearAuthSession,
  getAccessToken,
  loadAuthSession,
  saveAuthSession,
} from "@/lib/auth";


function buildToken(exp: number): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify({ exp }));
  return `${header}.${payload}.signature`;
}


afterEach(async () => {
  await clearAuthSession();
  vi.restoreAllMocks();
});


describe("auth session helpers", () => {
  it("saves and reloads a valid auth session", () => {
    vi.spyOn(Date, "now").mockReturnValue(1_700_000_000_000);

    const session = {
      access_token: buildToken(1_700_000_000 + 600),
      token_type: "bearer",
      user: {
        id: "user-1",
        email: "writer@example.com",
      },
    };

    saveAuthSession(session);

    expect(loadAuthSession()).toEqual(session);
    expect(getAccessToken()).toBe(session.access_token);
    expect(document.cookie).toContain("novel_agent_token=");
  });

  it("clears expired or invalid sessions", () => {
    vi.spyOn(Date, "now").mockReturnValue(1_700_000_000_000);
    window.localStorage.setItem(
      "long-novel-agent.auth",
      JSON.stringify({
        access_token: buildToken(1_700_000_000 - 60),
        token_type: "bearer",
        user: {
          id: "user-1",
          email: "writer@example.com",
        },
      }),
    );

    expect(loadAuthSession()).toBeNull();
    expect(window.localStorage.getItem("long-novel-agent.auth")).toBeNull();
  });
});
