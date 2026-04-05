import { describe, expect, it } from "vitest";

import {
  buildReviewCommentThreads,
  countWords,
  formatTaskEventLabel,
  summarizeTaskEventPayload,
} from "@/components/editor/formatters";


describe("editor formatters", () => {
  it("groups replies under their root comments", () => {
    const threads = buildReviewCommentThreads([
      {
        id: "root-1",
        parent_comment_id: null,
      },
      {
        id: "reply-1",
        parent_comment_id: "root-1",
      },
      {
        id: "root-2",
        parent_comment_id: null,
      },
    ] as never);

    expect(threads).toHaveLength(2);
    expect(threads[0].root.id).toBe("root-1");
    expect(threads[0].replies).toHaveLength(1);
    expect(threads[0].replies[0].id).toBe("reply-1");
  });

  it("summarizes task event payloads into compact badges", () => {
    const summary = summarizeTaskEventPayload({
      phase: "agent_pipeline",
      dispatch_strategy: "celery",
      agent_count: 4,
      overall_score: 0.82,
      truth_layer_status: "degraded",
      retrieval_backends: ["lexical", "qdrant"],
    });

    expect(summary).toContain("阶段 agent_pipeline");
    expect(summary).toContain("Celery Worker");
    expect(summary).toContain("Agent 4");
    expect(summary).toContain("综合 8.2/10");
  });

  it("keeps basic text formatting helpers stable", () => {
    expect(countWords("one two  three")).toBe(3);
    expect(countWords("   ")).toBe(0);
    expect(formatTaskEventLabel("generation_started")).toBe("Agent 生成");
    expect(formatTaskEventLabel("custom_event")).toBe("custom event");
  });
});
