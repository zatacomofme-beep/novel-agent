import { afterEach, describe, expect, it, vi } from "vitest";


afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});


describe("buildApiWebSocketUrl", () => {
  it("switches http base urls to ws and appends scalar params", async () => {
    const { buildApiWebSocketUrl } = await import("@/lib/api");
    const url = buildApiWebSocketUrl("/ws/tasks/abc", {
      token: "hello",
      empty: "",
      nullable: null,
    });

    expect(url).toBe("ws://localhost:8000/ws/tasks/abc?token=hello");
  });

  it("switches https base urls to wss and preserves repeated query params", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://novels.example.com/api");
    const { buildApiWebSocketUrl } = await import("@/lib/api");

    const url = buildApiWebSocketUrl("/ws/tasks/abc", {
      filter: ["queued", "running", ""],
      single: "ok",
    });

    expect(url).toBe(
      "wss://novels.example.com/ws/tasks/abc?filter=queued&filter=running&single=ok",
    );
  });
});
