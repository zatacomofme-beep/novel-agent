import { describe, expect, it } from "vitest";

import {
  buildStoryBibleHref,
  normalizeEntityLabels,
  resolveStoryBibleDeepLinkFocus,
  resolveStoryBibleSectionFromPlugin,
} from "@/lib/story-bible-deeplink";


describe("story bible deeplink helpers", () => {
  it("maps plugin keys to public story bible sections", () => {
    expect(resolveStoryBibleSectionFromPlugin("relationship")).toBe("characters");
    expect(resolveStoryBibleSectionFromPlugin("item")).toBe("items");
    expect(resolveStoryBibleSectionFromPlugin("timeline")).toBe("timeline_events");
    expect(resolveStoryBibleSectionFromPlugin("unknown")).toBeNull();
  });

  it("resolves focus modes from target metadata", () => {
    expect(
      resolveStoryBibleDeepLinkFocus({
        pluginKey: "item",
        actionScope: "story_bible",
      }),
    ).toBe("entity_editor");
    expect(
      resolveStoryBibleDeepLinkFocus({
        source: "story_bible_integrity",
      }),
    ).toBe("integrity");
    expect(resolveStoryBibleDeepLinkFocus({})).toBe("canon_snapshot");
  });

  it("builds deep links with normalized labels and section params", () => {
    const href = buildStoryBibleHref({
      projectId: "project-1",
      branchId: "branch-1",
      pluginKey: "item",
      source: "story_bible_integrity",
      actionScope: "story_bible",
      code: "item.owner_missing",
      entityLabels: ["  龙纹古戒  ", "", "   "],
    });

    expect(href).not.toBeNull();
    const url = new URL(href!, "http://localhost");
    expect(url.pathname).toBe("/dashboard/projects/project-1/story-room");
    expect(url.searchParams.get("branch_id")).toBe("branch-1");
    expect(url.searchParams.get("plugin")).toBe("item");
    expect(url.searchParams.get("source")).toBe("story_bible_integrity");
    expect(url.searchParams.get("action_scope")).toBe("story_bible");
    expect(url.searchParams.get("code")).toBe("item.owner_missing");
    expect(url.searchParams.get("section")).toBe("items");
    expect(url.searchParams.get("entity_label")).toBe("  龙纹古戒  ");
    expect(url.searchParams.get("focus")).toBe("entity_editor");
    expect(url.searchParams.get("stage")).toBe("knowledge");
    expect(url.searchParams.get("entry")).toBe("story_bible");
    expect(normalizeEntityLabels([" 甲 ", "", "乙"])).toEqual([" 甲 ", "乙"]);
    expect(buildStoryBibleHref({ projectId: null })).toBeNull();
  });
});
