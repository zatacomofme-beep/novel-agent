import { describe, expect, it } from "vitest";

import {
  analyzeStoryRoomLocalDraftRecovery,
  buildStoryRoomLocalDraftKey,
  summarizeStoryRoomLocalDraft,
} from "@/lib/story-room-local-draft";


describe("story room local draft helpers", () => {
  it("builds stable scope keys with sensible defaults", () => {
    expect(
      buildStoryRoomLocalDraftKey({
        projectId: "project-1",
        branchId: null,
        volumeId: null,
        chapterNumber: 7,
      }),
    ).toBe("story-room.local-draft:project-1:default:default:7");
  });

  it("summarizes snapshots into UI-friendly draft cards", () => {
    const summary = summarizeStoryRoomLocalDraft(
      "story-room.local-draft:project-1:main:vol-1:3",
      {
        projectId: "project-1",
        branchId: "main",
        volumeId: "vol-1",
        chapterNumber: 3,
        chapterTitle: "第三章 风起潮生",
        draftText: "  林舟握紧旧钥匙，忽然听见潮声从墙内传来。  ",
        outlineId: "outline-3",
        sourceChapterId: "chapter-3",
        sourceVersionNumber: 2,
        updatedAt: "2026-04-04T10:00:00Z",
      },
      "localStorage",
    );

    expect(summary.chapterTitle).toBe("第三章 风起潮生");
    expect(summary.charCount).toBe("林舟握紧旧钥匙，忽然听见潮声从墙内传来。".length);
    expect(summary.excerpt).toContain("林舟握紧旧钥匙");
    expect(summary.storageEngine).toBe("localStorage");
  });

  it("classifies recovery state against the current chapter baseline", () => {
    const snapshot = {
      projectId: "project-1",
      branchId: "main",
      volumeId: "vol-1",
      chapterNumber: 3,
      chapterTitle: "第三章 风起潮生",
      draftText: "新版正文",
      outlineId: "outline-3",
      sourceChapterId: "chapter-3",
      sourceVersionNumber: 4,
      updatedAt: "2026-04-04T10:00:00Z",
    };

    expect(
      analyzeStoryRoomLocalDraftRecovery(snapshot, {
        chapterId: "chapter-3",
        chapterTitle: "第三章 风起潮生",
        draftText: "新版正文",
        currentVersionNumber: 4,
      }),
    ).toEqual({ canRestore: false, state: "unchanged" });

    expect(
      analyzeStoryRoomLocalDraftRecovery(snapshot, {
        chapterId: "chapter-3",
        chapterTitle: "第三章 风起潮生",
        draftText: "旧版正文",
        currentVersionNumber: 3,
      }),
    ).toEqual({ canRestore: true, state: "local_newer" });

    expect(
      analyzeStoryRoomLocalDraftRecovery(
        {
          ...snapshot,
          sourceChapterId: "chapter-2",
        },
        {
          chapterId: "chapter-3",
          chapterTitle: "第三章 风起潮生",
          draftText: "旧版正文",
          currentVersionNumber: 3,
        },
      ),
    ).toEqual({ canRestore: true, state: "relinked" });
  });
});
