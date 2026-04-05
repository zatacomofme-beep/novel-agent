import { describe, expect, it } from "vitest";

import { buildUserFriendlyError, classifyError } from "@/lib/errors";


describe("error helpers", () => {
  it("classifies common auth, conflict, and network errors", () => {
    expect(classifyError(new Error("Authentication required.")).category).toBe("auth");
    expect(classifyError(new Error("Request failed with status 409")).category).toBe("conflict");
    expect(classifyError(new Error("ECONNREFUSED localhost:8000")).category).toBe("network");
  });

  it("builds user-facing messages from classified errors", () => {
    expect(buildUserFriendlyError(new Error("Request failed with status 403"))).toBe(
      "您没有权限执行此操作。",
    );
    expect(buildUserFriendlyError(new Error("Request failed with status 500"))).toBe(
      "服务器内部错误，请稍后重试。",
    );
    expect(buildUserFriendlyError("something odd happened")).toContain("something odd happened");
  });
});
