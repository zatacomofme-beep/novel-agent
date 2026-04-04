import { apiFetchWithAuth, downloadWithAuth } from "@/lib/api";
import type {
  Chapter,
  ChapterReviewWorkspace,
  ChapterSelectionRewriteResponse,
  ChapterVersion,
  RollbackResponse,
} from "@/types/api";

type ChapterCommentCreatePayload = {
  body: string;
  parent_comment_id?: string | null;
  assignee_user_id?: string | null;
  selection_start?: number | null;
  selection_end?: number | null;
  selection_text?: string | null;
};

type ChapterCommentUpdatePayload = {
  status?: string;
  assignee_user_id?: string | null;
};

type ChapterCheckpointCreatePayload = {
  checkpoint_type: string;
  title: string;
  description?: string | null;
};

type ChapterCheckpointUpdatePayload = {
  status: string;
  decision_note?: string | null;
};

type ChapterReviewDecisionCreatePayload = {
  verdict: string;
  summary: string;
  focus_points: string[];
};

type ChapterRewriteSelectionPayload = {
  selection_start: number;
  selection_end: number;
  instruction: string;
  create_version: boolean;
};

type ChapterCreatePayload = {
  chapter_number: number;
  volume_id: string | null;
  branch_id: string | null;
  title: string | null;
  content: string;
  outline: Record<string, unknown> | null;
  status: string;
  change_reason: string | null;
};

export async function fetchLegacyChapterReviewBundle(
  projectId: string,
  chapterId: string,
): Promise<{
  workspace: ChapterReviewWorkspace;
  versions: ChapterVersion[];
}> {
  const [workspace, versions] = await Promise.all([
    apiFetchWithAuth<ChapterReviewWorkspace>(
      `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/review-workspace`,
    ),
    apiFetchWithAuth<ChapterVersion[]>(
      `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/versions`,
    ),
  ]);

  return { workspace, versions };
}

export async function createLegacyChapterComment(
  projectId: string,
  chapterId: string,
  payload: ChapterCommentCreatePayload,
): Promise<void> {
  await apiFetchWithAuth(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/comments`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function updateLegacyChapterComment(
  projectId: string,
  chapterId: string,
  commentId: string,
  payload: ChapterCommentUpdatePayload,
): Promise<void> {
  await apiFetchWithAuth(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/comments/${commentId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export async function deleteLegacyChapterComment(
  projectId: string,
  chapterId: string,
  commentId: string,
): Promise<void> {
  await apiFetchWithAuth(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/comments/${commentId}`,
    {
      method: "DELETE",
    },
  );
}

export async function createLegacyChapterCheckpoint(
  projectId: string,
  chapterId: string,
  payload: ChapterCheckpointCreatePayload,
): Promise<void> {
  await apiFetchWithAuth(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/checkpoints`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function updateLegacyChapterCheckpoint(
  projectId: string,
  chapterId: string,
  checkpointId: string,
  payload: ChapterCheckpointUpdatePayload,
): Promise<void> {
  await apiFetchWithAuth(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/checkpoints/${checkpointId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export async function createLegacyChapterReviewDecision(
  projectId: string,
  chapterId: string,
  payload: ChapterReviewDecisionCreatePayload,
): Promise<void> {
  await apiFetchWithAuth(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/reviews`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function rollbackLegacyChapterVersion(
  projectId: string,
  chapterId: string,
  versionId: string,
): Promise<RollbackResponse> {
  return apiFetchWithAuth<RollbackResponse>(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/rollback/${versionId}`,
    {
      method: "POST",
    },
  );
}

export async function rewriteLegacyChapterSelection(
  projectId: string,
  chapterId: string,
  payload: ChapterRewriteSelectionPayload,
): Promise<ChapterSelectionRewriteResponse> {
  return apiFetchWithAuth<ChapterSelectionRewriteResponse>(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/rewrite-selection`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function updateLegacyChapter(
  projectId: string,
  chapterId: string,
  payload: Record<string, unknown>,
): Promise<Chapter> {
  return apiFetchWithAuth<Chapter>(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export async function createLegacyChapter(
  projectId: string,
  payload: ChapterCreatePayload,
): Promise<Chapter> {
  return apiFetchWithAuth<Chapter>(
    `/api/v1/projects/${projectId}/story-engine/chapters`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export async function exportLegacyChapter(
  projectId: string,
  chapterId: string,
  format: "md" | "txt",
): Promise<void> {
  await downloadWithAuth(
    `/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}/export?format=${format}`,
  );
}
