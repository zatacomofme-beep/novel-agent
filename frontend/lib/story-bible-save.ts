import { apiFetchWithAuth } from "@/lib/api";
import type {
  ProjectStructure,
  StoryBibleBranchItemUpsertPayload,
} from "@/types/api";

function resolvePreferredBranchId(structure: ProjectStructure): string | null {
  return structure.default_branch_id ?? structure.branches[0]?.id ?? null;
}

export function resolveStoryBibleSaveBranchId(
  structure: ProjectStructure,
  preferredBranchId?: string | null,
): string | null {
  const normalizedPreferredBranchId = preferredBranchId?.trim() ?? "";
  if (
    normalizedPreferredBranchId &&
    structure.branches.some((branch) => branch.id === normalizedPreferredBranchId)
  ) {
    return normalizedPreferredBranchId;
  }
  return resolvePreferredBranchId(structure);
}

export async function fetchStoryBibleSaveStructure(
  projectId: string,
): Promise<ProjectStructure> {
  return apiFetchWithAuth<ProjectStructure>(`/api/v1/projects/${projectId}/structure`);
}

type SaveStoryBibleBranchItemOptions = {
  branchId?: string | null;
};

export async function saveStoryBibleBranchItem(
  projectId: string,
  payload: StoryBibleBranchItemUpsertPayload,
  options: SaveStoryBibleBranchItemOptions = {},
): Promise<void> {
  let branchId = options.branchId?.trim() ?? "";
  if (!branchId) {
    const structure = await fetchStoryBibleSaveStructure(projectId);
    branchId = resolveStoryBibleSaveBranchId(structure) ?? "";
  }
  if (!branchId) {
    throw new Error("项目还没有可用分支，暂时无法保存到故事圣经。");
  }

  await apiFetchWithAuth(
    `/api/v1/projects/${projectId}/bible/item?branch_id=${branchId}`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function buildStoryBibleKey(prefix: string, label: string): string {
  const normalizedLabel = label.trim();
  if (!normalizedLabel) {
    return prefix;
  }
  return `${prefix}:${normalizedLabel}`.slice(0, 100);
}
