import { describe, expect, it } from "vitest";

import {
  buildStoryBibleKey,
  resolveStoryBibleSaveBranchId,
} from "@/lib/story-bible-save";


describe("story bible save helpers", () => {
  it("prefers an explicitly selected branch when it exists", () => {
    const branchId = resolveStoryBibleSaveBranchId(
      {
        default_branch_id: "branch-default",
        branches: [
          { id: "branch-default" },
          { id: "branch-side" },
        ],
      } as never,
      "branch-side",
    );

    expect(branchId).toBe("branch-side");
  });

  it("falls back to the default or first branch", () => {
    expect(
      resolveStoryBibleSaveBranchId(
        {
          default_branch_id: "branch-default",
          branches: [{ id: "branch-default" }],
        } as never,
        "missing-branch",
      ),
    ).toBe("branch-default");

    expect(
      resolveStoryBibleSaveBranchId(
        {
          default_branch_id: null,
          branches: [{ id: "branch-first" }],
        } as never,
      ),
    ).toBe("branch-first");
  });

  it("builds stable story bible entity keys", () => {
    expect(buildStoryBibleKey("item", " 龙纹古戒 ")).toBe("item:龙纹古戒");
    expect(buildStoryBibleKey("item", "   ")).toBe("item");
    expect(buildStoryBibleKey("x", "a".repeat(200))).toHaveLength(100);
  });
});
