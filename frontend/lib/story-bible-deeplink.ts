import type { StoryBibleSectionKey } from "@/types/api";

export type StoryBibleDeepLinkFocus =
  | "integrity"
  | "canon_snapshot"
  | "entity_editor";

export type StoryBibleDeepLinkTarget = {
  projectId: string | null | undefined;
  branchId?: string | null;
  pluginKey?: string | null;
  source?: string | null;
  actionScope?: string | null;
  code?: string | null;
  entityLabels?: string[] | null;
};

export function resolveStoryBibleSectionFromPlugin(
  pluginKey?: string | null,
): StoryBibleSectionKey | null {
  switch (pluginKey) {
    case "character":
    case "relationship":
      return "characters";
    case "item":
      return "items";
    case "faction":
      return "factions";
    case "location":
      return "locations";
    case "world_rule":
      return "world_settings";
    case "timeline":
      return "timeline_events";
    case "foreshadow":
      return "foreshadowing";
    default:
      return null;
  }
}

export function resolveStoryBibleDeepLinkFocus(
  target: Omit<StoryBibleDeepLinkTarget, "projectId" | "branchId">,
): StoryBibleDeepLinkFocus {
  if (target.actionScope === "story_bible") {
    return resolveStoryBibleSectionFromPlugin(target.pluginKey)
      ? "entity_editor"
      : "integrity";
  }
  if (target.source === "story_bible_integrity") {
    return "integrity";
  }
  return "canon_snapshot";
}

export function buildStoryBibleHref(
  target: StoryBibleDeepLinkTarget,
): string | null {
  if (!target.projectId) {
    return null;
  }

  const params = new URLSearchParams();
  if (target.branchId) {
    params.set("branch_id", target.branchId);
  }
  if (target.pluginKey) {
    params.set("plugin", target.pluginKey);
  }
  if (target.source) {
    params.set("source", target.source);
  }
  if (target.actionScope) {
    params.set("action_scope", target.actionScope);
  }
  if (target.code) {
    params.set("code", target.code);
  }

  const sectionKey = resolveStoryBibleSectionFromPlugin(target.pluginKey);
  if (sectionKey) {
    params.set("section", sectionKey);
  }

  const firstEntityLabel = normalizeEntityLabels(target.entityLabels)[0];
  if (firstEntityLabel) {
    params.set("entity_label", firstEntityLabel);
  }

  params.set(
    "focus",
    resolveStoryBibleDeepLinkFocus({
      pluginKey: target.pluginKey,
      source: target.source,
      actionScope: target.actionScope,
      code: target.code,
      entityLabels: target.entityLabels,
    }),
  );

  return `/dashboard/projects/${target.projectId}/bible?${params.toString()}`;
}

export function normalizeEntityLabels(
  labels: string[] | null | undefined,
): string[] {
  if (!Array.isArray(labels)) {
    return [];
  }
  return labels.filter((label) => typeof label === "string" && label.trim());
}
