"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetchWithAuth, downloadWithAuth } from "@/lib/api";
import type {
  Chapter,
  ChapterCheckpoint,
  ChapterReviewComment,
  ChapterReviewDecision,
  ChapterReviewWorkspace,
  ChapterSelectionRewriteResponse,
  TaskEvent,
  ChapterVersion,
  EvaluationReport,
  RollbackResponse,
  TaskState,
} from "@/types/api";

function prettyJson(value: Record<string, unknown> | null): string {
  return value ? JSON.stringify(value, null, 2) : "";
}

function countWords(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) {
    return 0;
  }
  return trimmed.split(/\s+/).length;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function formatTaskEventLabel(eventType: string): string {
  const labels: Record<string, string> = {
    queued: "任务排队",
    started: "开始执行",
    payload_built: "上下文装载",
    generation_started: "Agent 生成",
    outputs_persisting: "落库与评估",
    succeeded: "任务完成",
    failed: "任务失败",
  };

  return labels[eventType] ?? eventType.replace(/_/g, " ");
}

function summarizeTaskEventPayload(payload: Record<string, unknown> | null): string[] {
  if (!payload) {
    return [];
  }

  const summary: string[] = [];

  if (typeof payload.phase === "string") {
    summary.push(`阶段 ${payload.phase}`);
  }
  if (Array.isArray(payload.agents) && payload.agents.length > 0) {
    summary.push(`Agent ${payload.agents.join(", ")}`);
  } else if (typeof payload.agent_count === "number") {
    summary.push(`Agent ${payload.agent_count}`);
  }
  if (typeof payload.overall_score === "number") {
    summary.push(`综合 ${(payload.overall_score * 10).toFixed(1)}/10`);
  }
  if (typeof payload.initial_issue_count === "number") {
    summary.push(`初评 ${payload.initial_issue_count}`);
  }
  if (typeof payload.final_issue_count === "number") {
    summary.push(`复评 ${payload.final_issue_count}`);
  }
  if (typeof payload.revision_plan_steps === "number") {
    summary.push(`计划 ${payload.revision_plan_steps}`);
  }
  if (typeof payload.approved === "boolean") {
    summary.push(payload.approved ? "终审通过" : "终审拦截");
  }
  if (typeof payload.blocking_issue_count === "number") {
    summary.push(`阻塞 ${payload.blocking_issue_count}`);
  }
  if (Array.isArray(payload.revision_focus_dimensions) && payload.revision_focus_dimensions.length > 0) {
    summary.push(`聚焦 ${payload.revision_focus_dimensions.slice(0, 2).join(", ")}`);
  }
  if (typeof payload.ai_taste_score === "number") {
    summary.push(`AI味 ${payload.ai_taste_score.toFixed(2)}`);
  }
  if (typeof payload.issue_count === "number") {
    summary.push(`问题 ${payload.issue_count}`);
  }
  if (typeof payload.retrieval_items === "number") {
    summary.push(`检索 ${payload.retrieval_items}`);
  }
  if (Array.isArray(payload.retrieval_backends) && payload.retrieval_backends.length > 0) {
    summary.push(`后端 ${payload.retrieval_backends.join(", ")}`);
  }
  if (Array.isArray(payload.fallback_agents) && payload.fallback_agents.length > 0) {
    summary.push(`Fallback ${payload.fallback_agents.join(", ")}`);
  }
  if (Array.isArray(payload.remote_error_types) && payload.remote_error_types.length > 0) {
    summary.push(`错误 ${payload.remote_error_types.join(", ")}`);
  }
  if (typeof payload.revised === "boolean") {
    summary.push(payload.revised ? "已修订" : "未修订");
  }
  if (typeof payload.chapter_status === "string") {
    summary.push(`状态 ${payload.chapter_status}`);
  }
  if (typeof payload.query === "string" && payload.query.trim()) {
    const shortenedQuery =
      payload.query.length > 36 ? `${payload.query.slice(0, 36)}...` : payload.query;
    summary.push(`Query ${shortenedQuery}`);
  }

  return summary.slice(0, 4);
}

function formatMetricLabel(key: string): string {
  const labels: Record<string, string> = {
    fluency: "流畅度",
    vocabulary_richness: "词汇丰富度",
    sentence_variation: "句式变化",
    plot_tightness: "情节紧凑度",
    conflict_intensity: "冲突强度",
    suspense: "悬念",
    character_consistency: "人物一致性",
    world_consistency: "世界一致性",
    logic_coherence: "逻辑连贯",
    timeline_consistency: "时间线一致性",
    emotional_resonance: "情感共鸣",
    imagery: "意象",
    dialogue_quality: "对话质量",
    theme_depth: "主题深度",
    ai_taste_score: "AI 味",
  };
  return labels[key] ?? key;
}

function severityTone(severity: string): string {
  if (severity === "high") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (severity === "medium") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function approvalTone(approved: boolean): string {
  if (approved) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  return "border-amber-200 bg-amber-50 text-amber-700";
}

function reviewVerdictTone(verdict: string): string {
  if (verdict === "approved") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (verdict === "blocked") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  return "border-amber-200 bg-amber-50 text-amber-700";
}

function formatReviewVerdict(verdict: string): string {
  const labels: Record<string, string> = {
    approved: "已通过",
    changes_requested: "需修改",
    blocked: "阻塞",
  };
  return labels[verdict] ?? verdict;
}

function formatRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    owner: "Owner",
    editor: "Editor",
    reviewer: "Reviewer",
    viewer: "Viewer",
  };
  return labels[role] ?? role;
}

function checkpointStatusTone(status: string): string {
  if (status === "approved") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (status === "rejected") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "cancelled") {
    return "border-black/10 bg-white text-black/55";
  }
  return "border-amber-200 bg-amber-50 text-amber-700";
}

function formatCheckpointStatus(status: string): string {
  const labels: Record<string, string> = {
    pending: "待确认",
    approved: "已通过",
    rejected: "已驳回",
    cancelled: "已取消",
  };
  return labels[status] ?? status;
}

function formatCheckpointType(type: string): string {
  const labels: Record<string, string> = {
    story_turn: "关键转折",
    outline_gate: "大纲关卡",
    quality_gate: "质量关卡",
    branch_decision: "分支决策",
    manual_gate: "人工确认",
  };
  return labels[type] ?? type;
}

function reviewTimelineTone(kind: "comment" | "decision" | "checkpoint", status: string): string {
  if (kind === "decision") {
    return reviewVerdictTone(status);
  }
  if (kind === "checkpoint") {
    return checkpointStatusTone(status);
  }
  if (status === "resolved") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  return "border-amber-200 bg-amber-50 text-amber-700";
}

function finalGateTone(status: string): string {
  if (status === "blocked_rejected") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "blocked_review") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "blocked_pending") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function formatFinalGateStatus(status: string): string {
  const labels: Record<string, string> = {
    ready: "Final 可放行",
    blocked_pending: "Final 待确认",
    blocked_rejected: "Final 被驳回",
    blocked_review: "Review 未通过",
  };
  return labels[status] ?? status;
}

function buildFinalGateSummary(chapter: Chapter | null): string {
  if (!chapter) {
    return "正在同步审批门禁状态。";
  }
  if (chapter.final_gate_status === "blocked_rejected") {
    return `当前有 ${chapter.rejected_checkpoint_count} 个被驳回的 checkpoint，章节不能进入 final。`;
  }
  if (chapter.final_gate_status === "blocked_pending") {
    return `当前还有 ${chapter.pending_checkpoint_count} 个待确认 checkpoint，章节不能进入 final。`;
  }
  if (chapter.final_gate_status === "blocked_review") {
    if (chapter.latest_review_verdict === "blocked") {
      return "最新人工审阅结论为阻塞，章节不能进入 final。";
    }
    return "最新人工审阅结论仍要求修改，章节不能进入 final。";
  }
  if (chapter.latest_checkpoint_title) {
    return "所有 checkpoint 已闭环，当前可以进入 final。";
  }
  return "当前没有 checkpoint 阻塞 final 状态。";
}

function buildFinalGateSaveError(chapter: Chapter | null): string {
  if (!chapter) {
    return "章节审批门禁状态尚未同步，暂时不能进入 final。";
  }
  return chapter.final_gate_reason ?? buildFinalGateSummary(chapter);
}

type CommentAnchor = {
  selectionEnd: number;
  selectionStart: number;
  selectionText: string;
};

type ReviewTimelineItem =
  | {
      id: string;
      itemType: "comment";
      timestamp: string;
      title: string;
      subtitle: string;
      body: string;
      toneClass: string;
      comment: ChapterReviewComment;
    }
  | {
      id: string;
      itemType: "decision";
      timestamp: string;
      title: string;
      subtitle: string;
      body: string;
      toneClass: string;
      decision: ChapterReviewDecision;
    }
  | {
      id: string;
      itemType: "checkpoint";
      timestamp: string;
      title: string;
      subtitle: string;
      body: string;
      toneClass: string;
      checkpoint: ChapterCheckpoint;
    };

type ReviewCommentThread = {
  root: ChapterReviewComment;
  replies: ChapterReviewComment[];
};

function formatCommentTimelineTitle(comment: ChapterReviewComment): string {
  if (comment.parent_comment_id) {
    return comment.status === "resolved" ? "回复已解决" : "新增回复";
  }
  return comment.status === "resolved" ? "批注已解决" : "新增批注";
}

function buildReviewCommentThreads(
  comments: ChapterReviewComment[],
): ReviewCommentThread[] {
  const roots: ChapterReviewComment[] = [];
  const rootIds = new Set<string>();
  const repliesByParent: Record<string, ChapterReviewComment[]> = {};

  for (const comment of comments) {
    if (comment.parent_comment_id) {
      continue;
    }
    roots.push(comment);
    rootIds.add(comment.id);
  }

  for (const comment of comments) {
    if (!comment.parent_comment_id) {
      continue;
    }
    if (!rootIds.has(comment.parent_comment_id)) {
      roots.push(comment);
      rootIds.add(comment.id);
      continue;
    }
    repliesByParent[comment.parent_comment_id] = [
      ...(repliesByParent[comment.parent_comment_id] ?? []),
      comment,
    ];
  }

  return roots.map((root) => ({
    root,
    replies: repliesByParent[root.id] ?? [],
  }));
}

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws";

export default function ChapterEditorPage() {
  const params = useParams<{ chapterId: string }>();
  const chapterId = params.chapterId;

  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [versions, setVersions] = useState<ChapterVersion[]>([]);
  const [title, setTitle] = useState("");
  const [status, setStatus] = useState("draft");
  const [content, setContent] = useState("");
  const [outlineText, setOutlineText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rollingBack, setRollingBack] = useState<string | null>(null);
  const [taskState, setTaskState] = useState<TaskState | null>(null);
  const [taskEvents, setTaskEvents] = useState<TaskEvent[]>([]);
  const [startingTask, setStartingTask] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<"md" | "txt" | null>(null);
  const [evaluating, setEvaluating] = useState(false);
  const [evaluationReport, setEvaluationReport] = useState<EvaluationReport | null>(null);
  const [reviewWorkspace, setReviewWorkspace] = useState<ChapterReviewWorkspace | null>(null);
  const [checkpointType, setCheckpointType] = useState("story_turn");
  const [checkpointTitle, setCheckpointTitle] = useState("");
  const [checkpointDescription, setCheckpointDescription] = useState("");
  const [submittingCheckpoint, setSubmittingCheckpoint] = useState(false);
  const [updatingCheckpointId, setUpdatingCheckpointId] = useState<string | null>(null);
  const [checkpointStatusFilter, setCheckpointStatusFilter] = useState("all");
  const [checkpointTypeFilter, setCheckpointTypeFilter] = useState("all");
  const [focusedCheckpointId, setFocusedCheckpointId] = useState<string | null>(null);
  const [rewriteInstruction, setRewriteInstruction] = useState("");
  const [rewriteAnchor, setRewriteAnchor] = useState<CommentAnchor | null>(null);
  const [rewritingSelection, setRewritingSelection] = useState(false);
  const [lastRewriteResult, setLastRewriteResult] =
    useState<ChapterSelectionRewriteResponse | null>(null);
  const [commentBody, setCommentBody] = useState("");
  const [commentAnchor, setCommentAnchor] = useState<CommentAnchor | null>(null);
  const [submittingComment, setSubmittingComment] = useState(false);
  const [updatingCommentId, setUpdatingCommentId] = useState<string | null>(null);
  const [activeReplyCommentId, setActiveReplyCommentId] = useState<string | null>(null);
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({});
  const [submittingReplyToCommentId, setSubmittingReplyToCommentId] = useState<
    string | null
  >(null);
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [decisionVerdict, setDecisionVerdict] = useState("changes_requested");
  const [decisionSummary, setDecisionSummary] = useState("");
  const [decisionFocusText, setDecisionFocusText] = useState("");
  const [compareLeftVersionId, setCompareLeftVersionId] = useState<string>("");
  const [compareRightVersionId, setCompareRightVersionId] = useState<string>("");
  const lastCompletedTaskId = useRef<string | null>(null);
  const contentRef = useRef<HTMLTextAreaElement | null>(null);
  const commentListRef = useRef<HTMLDivElement | null>(null);
  const versionCompareRef = useRef<HTMLElement | null>(null);
  const activeTaskId = taskState?.task_id ?? null;
  const activeTaskStatus = taskState?.status ?? null;

  const canEditChapter = reviewWorkspace?.can_edit_chapter ?? false;
  const canRunGeneration = reviewWorkspace?.can_run_generation ?? false;
  const canRunEvaluation = reviewWorkspace?.can_run_evaluation ?? false;
  const canComment = reviewWorkspace?.can_comment ?? false;
  const canDecide = reviewWorkspace?.can_decide ?? false;
  const canRequestCheckpoint = reviewWorkspace?.can_request_checkpoint ?? false;
  const canDecideCheckpoint = reviewWorkspace?.can_decide_checkpoint ?? false;

  const loadTaskEvents = useCallback(async (taskId: string) => {
    try {
      const events = await apiFetchWithAuth<TaskEvent[]>(
        `/api/v1/tasks/${taskId}/events`,
      );
      setTaskEvents(events);
    } catch {
      // Keep the last successful timeline snapshot instead of surfacing noisy background errors.
    }
  }, []);

  const refreshTaskState = useCallback(async () => {
    if (!activeTaskId) {
      return;
    }
    try {
      const nextTaskState = await apiFetchWithAuth<TaskState>(
        `/api/v1/tasks/${activeTaskId}`,
      );
      setTaskState(nextTaskState);
      void loadTaskEvents(nextTaskState.task_id);
    } catch (taskError) {
      setError(
        taskError instanceof Error
          ? taskError.message
          : "Failed to refresh task state.",
      );
    }
  }, [activeTaskId, loadTaskEvents]);

  const loadReviewWorkspace = useCallback(async () => {
    try {
      const reviewData = await apiFetchWithAuth<ChapterReviewWorkspace>(
        `/api/v1/chapters/${chapterId}/review-workspace`,
      );
      setReviewWorkspace(reviewData);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load chapter review workspace.",
      );
    }
  }, [chapterId]);

  const refreshChapterStatusSnapshot = useCallback(async () => {
    const chapterData = await apiFetchWithAuth<Chapter>(`/api/v1/chapters/${chapterId}`);
    setChapter((current) =>
      current
        ? {
            ...current,
            status: chapterData.status,
            pending_checkpoint_count: chapterData.pending_checkpoint_count,
            rejected_checkpoint_count: chapterData.rejected_checkpoint_count,
            latest_checkpoint_status: chapterData.latest_checkpoint_status,
            latest_checkpoint_title: chapterData.latest_checkpoint_title,
            latest_review_verdict: chapterData.latest_review_verdict,
            latest_review_summary: chapterData.latest_review_summary,
            review_gate_blocked: chapterData.review_gate_blocked,
            final_ready: chapterData.final_ready,
            final_gate_status: chapterData.final_gate_status,
            final_gate_reason: chapterData.final_gate_reason,
          }
        : chapterData,
    );
    setStatus(chapterData.status);
  }, [chapterId]);

  const loadEditor = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const [chapterData, versionData, taskData, reviewData] = await Promise.all([
        apiFetchWithAuth<Chapter>(`/api/v1/chapters/${chapterId}`),
        apiFetchWithAuth<ChapterVersion[]>(`/api/v1/chapters/${chapterId}/versions`),
        apiFetchWithAuth<TaskState[]>(`/api/v1/chapters/${chapterId}/tasks`),
        apiFetchWithAuth<ChapterReviewWorkspace>(
          `/api/v1/chapters/${chapterId}/review-workspace`,
        ),
      ]);
      setChapter(chapterData);
      setVersions(versionData);
      setTaskState(taskData[0] ?? null);
      setReviewWorkspace(reviewData);
      setTitle(chapterData.title ?? "");
      setStatus(chapterData.status);
      setContent(chapterData.content);
      setOutlineText(prettyJson(chapterData.outline));
      if (versionData.length > 0) {
        const newest = versionData[versionData.length - 1];
        const previous = versionData[versionData.length - 2] ?? newest;
        setCompareLeftVersionId(newest.id);
        setCompareRightVersionId(previous.id);
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load chapter editor.",
      );
    } finally {
      setLoading(false);
    }
  }, [chapterId]);

  useEffect(() => {
    void loadEditor();
  }, [loadEditor]);

  useEffect(() => {
    if (!activeTaskId || !activeTaskStatus || !["queued", "running"].includes(activeTaskStatus)) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void refreshTaskState();
    }, 2000);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [activeTaskId, activeTaskStatus, refreshTaskState]);

  useEffect(() => {
    if (!activeTaskId || !activeTaskStatus || !["queued", "running"].includes(activeTaskStatus)) {
      return;
    }

    const socket = new WebSocket(`${WS_URL}/tasks/${activeTaskId}`);
    socket.onmessage = (event) => {
      try {
        const nextState = JSON.parse(event.data) as TaskState;
        setTaskState(nextState);
      } catch {
        // Ignore malformed websocket messages and keep polling fallback alive.
      }
    };

    return () => {
      socket.close();
    };
  }, [activeTaskId, activeTaskStatus]);

  useEffect(() => {
    if (!taskState || taskState.status !== "succeeded") {
      return;
    }
    if (lastCompletedTaskId.current === taskState.task_id) {
      return;
    }

    lastCompletedTaskId.current = taskState.task_id;
    const evaluation = taskState.result?.evaluation as
      | EvaluationReport
      | undefined;
    if (evaluation) {
      setEvaluationReport(evaluation);
    }
    void loadEditor();
  }, [loadEditor, taskState]);

  useEffect(() => {
    if (!taskState) {
      setTaskEvents([]);
      return;
    }
    void loadTaskEvents(taskState.task_id);
  }, [loadTaskEvents, taskState]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSuccess(null);

    if (status === "final" && !chapter?.final_ready) {
      setSaving(false);
      setError(buildFinalGateSaveError(chapter));
      return;
    }

    let outlinePayload: Record<string, unknown> | null = null;
    if (outlineText.trim()) {
      try {
        outlinePayload = JSON.parse(outlineText) as Record<string, unknown>;
      } catch (parseError) {
        setSaving(false);
        setError(
          parseError instanceof Error
            ? `Outline JSON 解析失败：${parseError.message}`
            : "Outline JSON 解析失败。",
        );
        return;
      }
    }

    try {
      const updated = await apiFetchWithAuth<Chapter>(`/api/v1/chapters/${chapterId}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: title || null,
          status,
          content,
          outline: outlinePayload,
          change_reason: "Updated from chapter editor",
          create_version: true,
        }),
      });
      setChapter(updated);
      setSuccess("章节已保存，若正文发生变化则已创建新版本。");
      const nextVersions = await apiFetchWithAuth<ChapterVersion[]>(
        `/api/v1/chapters/${chapterId}/versions`,
      );
      setVersions(nextVersions);
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Failed to save chapter.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleRollback(versionId: string) {
    setRollingBack(versionId);
    setError(null);
    setSuccess(null);
    try {
      const result = await apiFetchWithAuth<RollbackResponse>(
        `/api/v1/chapters/${chapterId}/rollback/${versionId}`,
        { method: "POST" },
      );
      setChapter(result.chapter);
      setTitle(result.chapter.title ?? "");
      setStatus(result.chapter.status);
      setContent(result.chapter.content);
      setOutlineText(prettyJson(result.chapter.outline));
      const nextVersions = await apiFetchWithAuth<ChapterVersion[]>(
        `/api/v1/chapters/${chapterId}/versions`,
      );
      setVersions(nextVersions);
      setSuccess(
        `已回滚，并生成新版本 #${result.restored_version.version_number} 记录回滚结果。`,
      );
    } catch (rollbackError) {
      setError(
        rollbackError instanceof Error
          ? rollbackError.message
          : "Failed to rollback chapter.",
      );
    } finally {
      setRollingBack(null);
    }
  }

  async function handleCreateGenerationTask() {
    setStartingTask(true);
    setError(null);
    setSuccess(null);
    try {
      const task = await apiFetchWithAuth<TaskState>(
        `/api/v1/chapters/${chapterId}/generate`,
        { method: "POST" },
      );
      setTaskState(task);
      setSuccess("生成任务已创建，后台将执行协调器流程并自动更新章节。");
    } catch (taskError) {
      setError(
        taskError instanceof Error
          ? taskError.message
          : "Failed to create generation task.",
      );
    } finally {
      setStartingTask(false);
    }
  }

  async function handleExportChapter(format: "md" | "txt") {
    setExportingFormat(format);
    setError(null);
    setSuccess(null);
    try {
      await downloadWithAuth(`/api/v1/chapters/${chapterId}/export?format=${format}`);
      setSuccess(`章节已导出为 ${format.toUpperCase()}。`);
    } catch (exportError) {
      setError(
        exportError instanceof Error
          ? exportError.message
          : "Failed to export chapter.",
      );
    } finally {
      setExportingFormat(null);
    }
  }

  const compareLeftVersion =
    versions.find((version) => version.id === compareLeftVersionId) ?? null;
  const compareRightVersion =
    versions.find((version) => version.id === compareRightVersionId) ?? null;
  const taskInitialReview =
    taskState?.result?.initial_review as Record<string, unknown> | undefined;
  const taskFinalReview =
    (taskState?.result?.final_review as Record<string, unknown> | undefined) ??
    (taskState?.result?.review as Record<string, unknown> | undefined);
  const taskRevisionFocus = Array.isArray(taskState?.result?.revision_focus)
    ? (taskState?.result?.revision_focus as Record<string, unknown>[])
    : [];
  const taskRevisionPlan =
    taskState?.result?.revision_plan as Record<string, unknown> | undefined;
  const taskDebateSummary =
    taskState?.result?.debate_summary as Record<string, unknown> | undefined;
  const taskApproval =
    taskState?.result?.approval as Record<string, unknown> | undefined;
  const compareDeltaWords =
    (compareLeftVersion ? countWords(compareLeftVersion.content) : 0) -
    (compareRightVersion ? countWords(compareRightVersion.content) : 0);
  const compareDeltaChars =
    (compareLeftVersion?.content.length ?? 0) -
    (compareRightVersion?.content.length ?? 0);
  const reviewComments = reviewWorkspace?.comments ?? [];
  const reviewDecisions = reviewWorkspace?.decisions ?? [];
  const reviewCheckpoints = reviewWorkspace?.checkpoints ?? [];
  const latestReviewDecision = reviewWorkspace?.latest_decision ?? null;
  const latestPendingCheckpoint = reviewWorkspace?.latest_pending_checkpoint ?? null;
  const commentsByVersionNumber = reviewComments.reduce<Record<number, number>>(
    (accumulator, comment) => {
      accumulator[comment.chapter_version_number] =
        (accumulator[comment.chapter_version_number] ?? 0) + 1;
      return accumulator;
    },
    {},
  );
  const reviewCommentThreads = buildReviewCommentThreads(reviewComments);
  const filteredCheckpoints = reviewCheckpoints.filter((checkpoint) => {
    if (
      checkpointStatusFilter !== "all" &&
      checkpoint.status !== checkpointStatusFilter
    ) {
      return false;
    }
    if (
      checkpointTypeFilter !== "all" &&
      checkpoint.checkpoint_type !== checkpointTypeFilter
    ) {
      return false;
    }
    return true;
  });
  const focusedCheckpoint =
    reviewCheckpoints.find((checkpoint) => checkpoint.id === focusedCheckpointId) ?? null;
  const visibleCommentThreads = focusedCheckpoint
    ? reviewCommentThreads.filter((thread) =>
        [thread.root, ...thread.replies].some(
          (comment) =>
            comment.chapter_version_number === focusedCheckpoint.chapter_version_number,
        ),
      )
    : reviewCommentThreads;
  const visibleCommentCount = visibleCommentThreads.reduce(
    (accumulator, thread) => accumulator + 1 + thread.replies.length,
    0,
  );
  const reviewTimelineItems: ReviewTimelineItem[] = [
    ...reviewComments.map((comment) => ({
      id: comment.id,
      itemType: "comment" as const,
      timestamp: comment.updated_at,
      title: formatCommentTimelineTitle(comment),
      subtitle: `${comment.author_email || "Unknown"} · Version ${
        comment.chapter_version_number
      }${comment.parent_comment_id ? " · 线程回复" : ""}`,
      body: comment.body,
      toneClass: reviewTimelineTone("comment", comment.status),
      comment,
    })),
    ...reviewDecisions.map((decision) => ({
      id: decision.id,
      itemType: "decision" as const,
      timestamp: decision.created_at,
      title: `审阅结论 · ${formatReviewVerdict(decision.verdict)}`,
      subtitle: `${decision.reviewer_email || "Unknown"} · Version ${decision.chapter_version_number}`,
      body: decision.summary,
      toneClass: reviewTimelineTone("decision", decision.verdict),
      decision,
    })),
    ...reviewCheckpoints.map((checkpoint) => ({
      id: checkpoint.id,
      itemType: "checkpoint" as const,
      timestamp: checkpoint.updated_at,
      title: `Checkpoint · ${checkpoint.title}`,
      subtitle: `${formatCheckpointType(checkpoint.checkpoint_type)} · Version ${checkpoint.chapter_version_number}`,
      body:
        checkpoint.decision_note ||
        checkpoint.description ||
        "该关键节点暂无额外说明。",
      toneClass: reviewTimelineTone("checkpoint", checkpoint.status),
      checkpoint,
    })),
  ].sort(
    (left, right) =>
      new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime(),
  );

  function readCurrentSelection(errorMessage: string): CommentAnchor | null {
    const textarea = contentRef.current;
    if (!textarea) {
      return null;
    }
    const selectionStart = textarea.selectionStart;
    const selectionEnd = textarea.selectionEnd;
    if (selectionStart === selectionEnd) {
      setError(errorMessage);
      return null;
    }
    setError(null);
    return {
      selectionStart,
      selectionEnd,
      selectionText: textarea.value.slice(selectionStart, selectionEnd),
    };
  }

  function captureCommentAnchor() {
    const selection = readCurrentSelection("先在正文里选中一段文本，再创建锚点批注。");
    if (!selection) {
      setCommentAnchor(null);
      return;
    }
    setCommentAnchor(selection);
  }

  function captureRewriteAnchor() {
    const selection = readCurrentSelection("先在正文里选中一段文本，再发起局部重写。");
    if (!selection) {
      setRewriteAnchor(null);
      return;
    }
    setRewriteAnchor(selection);
  }

  async function handleCreateComment() {
    if (!commentBody.trim()) {
      setError("请输入批注内容。");
      return;
    }

    setSubmittingComment(true);
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<ChapterReviewComment>(`/api/v1/chapters/${chapterId}/comments`, {
        method: "POST",
        body: JSON.stringify({
          body: commentBody.trim(),
          selection_start: commentAnchor?.selectionStart ?? null,
          selection_end: commentAnchor?.selectionEnd ?? null,
          selection_text: commentAnchor?.selectionText ?? null,
        }),
      });
      setCommentBody("");
      setCommentAnchor(null);
      setSuccess("审阅批注已添加。");
      await loadReviewWorkspace();
    } catch (commentError) {
      setError(
        commentError instanceof Error
          ? commentError.message
          : "Failed to create chapter comment.",
      );
    } finally {
      setSubmittingComment(false);
    }
  }

  function handleStartReply(commentId: string) {
    setActiveReplyCommentId(commentId);
    setReplyDrafts((current) => ({
      ...current,
      [commentId]: current[commentId] ?? "",
    }));
    setError(null);
    setSuccess(null);
  }

  function handleCancelReply() {
    setActiveReplyCommentId(null);
    setError(null);
  }

  async function handleCreateReply(comment: ChapterReviewComment) {
    const replyBody = (replyDrafts[comment.id] ?? "").trim();
    if (!replyBody) {
      setError("请输入回复内容。");
      return;
    }

    setSubmittingReplyToCommentId(comment.id);
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<ChapterReviewComment>(`/api/v1/chapters/${chapterId}/comments`, {
        method: "POST",
        body: JSON.stringify({
          body: replyBody,
          parent_comment_id: comment.id,
        }),
      });
      setReplyDrafts((current) => ({
        ...current,
        [comment.id]: "",
      }));
      setActiveReplyCommentId(null);
      setSuccess(
        comment.parent_comment_id
          ? "回复已添加，并归入当前批注线程。"
          : "线程回复已添加。",
      );
      await loadReviewWorkspace();
    } catch (commentError) {
      setError(
        commentError instanceof Error
          ? commentError.message
          : "Failed to create chapter comment reply.",
      );
    } finally {
      setSubmittingReplyToCommentId(null);
    }
  }

  async function handleToggleCommentStatus(comment: ChapterReviewComment) {
    setUpdatingCommentId(comment.id);
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<ChapterReviewComment>(
        `/api/v1/chapters/${chapterId}/comments/${comment.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status: comment.status === "open" ? "resolved" : "open",
          }),
        },
      );
      setSuccess(comment.status === "open" ? "批注已标记为已解决。" : "批注已重新打开。");
      await loadReviewWorkspace();
    } catch (commentError) {
      setError(
        commentError instanceof Error
          ? commentError.message
          : "Failed to update chapter comment.",
      );
    } finally {
      setUpdatingCommentId(null);
    }
  }

  async function handleDeleteComment(comment: ChapterReviewComment) {
    const confirmed = window.confirm("确定删除这条批注吗？");
    if (!confirmed) {
      return;
    }

    setUpdatingCommentId(comment.id);
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<void>(`/api/v1/chapters/${chapterId}/comments/${comment.id}`, {
        method: "DELETE",
      });
      setSuccess("批注已删除。");
      await loadReviewWorkspace();
    } catch (commentError) {
      setError(
        commentError instanceof Error
          ? commentError.message
          : "Failed to delete chapter comment.",
      );
    } finally {
      setUpdatingCommentId(null);
    }
  }

  async function handleCreateReviewDecision() {
    if (!decisionSummary.trim()) {
      setError("请输入审阅结论摘要。");
      return;
    }

    setSubmittingDecision(true);
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<ChapterReviewDecision>(`/api/v1/chapters/${chapterId}/reviews`, {
        method: "POST",
        body: JSON.stringify({
          verdict: decisionVerdict,
          summary: decisionSummary.trim(),
          focus_points: decisionFocusText
            .split(/[\n,，]/)
            .map((item) => item.trim())
            .filter(Boolean),
        }),
      });
      setDecisionSummary("");
      setDecisionFocusText("");
      setSuccess("审阅结论已记录。");
      await Promise.all([loadReviewWorkspace(), refreshChapterStatusSnapshot()]);
    } catch (decisionError) {
      setError(
        decisionError instanceof Error
          ? decisionError.message
          : "Failed to create chapter review decision.",
      );
    } finally {
      setSubmittingDecision(false);
    }
  }

  async function handleCreateCheckpoint() {
    if (!checkpointTitle.trim()) {
      setError("请输入关键节点标题。");
      return;
    }

    setSubmittingCheckpoint(true);
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<ChapterCheckpoint>(`/api/v1/chapters/${chapterId}/checkpoints`, {
        method: "POST",
        body: JSON.stringify({
          checkpoint_type: checkpointType,
          title: checkpointTitle.trim(),
          description: checkpointDescription.trim() || null,
        }),
      });
      setCheckpointTitle("");
      setCheckpointDescription("");
      setSuccess("关键节点确认请求已创建。");
      await Promise.all([loadReviewWorkspace(), refreshChapterStatusSnapshot()]);
    } catch (checkpointError) {
      setError(
        checkpointError instanceof Error
          ? checkpointError.message
          : "Failed to create chapter checkpoint.",
      );
    } finally {
      setSubmittingCheckpoint(false);
    }
  }

  async function handleUpdateCheckpoint(
    checkpoint: ChapterCheckpoint,
    status: "approved" | "rejected" | "cancelled",
  ) {
    const needsNote = status !== "approved";
    const decisionNote = needsNote
      ? window.prompt(
          status === "rejected" ? "填写驳回原因：" : "填写取消原因：",
          checkpoint.decision_note ?? "",
        )
      : checkpoint.decision_note ?? "";

    if (needsNote && decisionNote === null) {
      return;
    }

    setUpdatingCheckpointId(checkpoint.id);
    setError(null);
    setSuccess(null);
    try {
      await apiFetchWithAuth<ChapterCheckpoint>(
        `/api/v1/chapters/${chapterId}/checkpoints/${checkpoint.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            status,
            decision_note: decisionNote?.trim() || null,
          }),
        },
      );
      setSuccess(
        status === "approved"
          ? "关键节点已确认通过。"
          : status === "rejected"
            ? "关键节点已驳回。"
            : "关键节点已取消。",
      );
      await Promise.all([loadReviewWorkspace(), refreshChapterStatusSnapshot()]);
    } catch (checkpointError) {
      setError(
        checkpointError instanceof Error
          ? checkpointError.message
          : "Failed to update chapter checkpoint.",
      );
    } finally {
      setUpdatingCheckpointId(null);
    }
  }

  async function handleRewriteSelection() {
    if (!rewriteAnchor) {
      setError("先载入需要重写的正文选区。");
      return;
    }
    if (!rewriteInstruction.trim()) {
      setError("请输入局部重写指令。");
      return;
    }

    setRewritingSelection(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await apiFetchWithAuth<ChapterSelectionRewriteResponse>(
        `/api/v1/chapters/${chapterId}/rewrite-selection`,
        {
          method: "POST",
          body: JSON.stringify({
            selection_start: rewriteAnchor.selectionStart,
            selection_end: rewriteAnchor.selectionEnd,
            instruction: rewriteInstruction.trim(),
            create_version: true,
          }),
        },
      );
      setLastRewriteResult(result);
      setChapter(result.chapter);
      setTitle(result.chapter.title ?? "");
      setStatus(result.chapter.status);
      setContent(result.chapter.content);
      setOutlineText(prettyJson(result.chapter.outline));
      setRewriteAnchor({
        selectionStart: result.selection_start,
        selectionEnd: result.rewritten_selection_end,
        selectionText: result.rewritten_text,
      });
      setRewriteInstruction("");
      const nextVersions = await apiFetchWithAuth<ChapterVersion[]>(
        `/api/v1/chapters/${chapterId}/versions`,
      );
      setVersions(nextVersions);
      if (nextVersions.length > 0) {
        const newest = nextVersions[nextVersions.length - 1];
        const previous = nextVersions[nextVersions.length - 2] ?? newest;
        setCompareLeftVersionId(newest.id);
        setCompareRightVersionId(previous.id);
      }
      await loadReviewWorkspace();
      setSuccess(
        `局部重写已写回章节，并创建新版本。引用相关批注 ${result.related_comment_count} 条。`,
      );
    } catch (rewriteError) {
      setError(
        rewriteError instanceof Error
          ? rewriteError.message
          : "Failed to rewrite selected chapter passage.",
      );
    } finally {
      setRewritingSelection(false);
    }
  }

  async function handleEvaluate() {
    setEvaluating(true);
    setError(null);
    setSuccess(null);
    try {
      const report = await apiFetchWithAuth<EvaluationReport>(
        `/api/v1/chapters/${chapterId}/evaluate`,
        { method: "POST" },
      );
      setEvaluationReport(report);
      setSuccess("章节评估已完成。");
      const refreshed = await apiFetchWithAuth<Chapter>(`/api/v1/chapters/${chapterId}`);
      setChapter(refreshed);
    } catch (evaluationError) {
      setError(
        evaluationError instanceof Error
          ? evaluationError.message
          : "Failed to evaluate chapter.",
      );
    } finally {
      setEvaluating(false);
    }
  }

  function handleFocusCheckpointComments(checkpoint: ChapterCheckpoint) {
    setFocusedCheckpointId(checkpoint.id);
    setError(null);
    setSuccess(`已切到 checkpoint「${checkpoint.title}」相关的批注线程上下文。`);
    window.requestAnimationFrame(() => {
      commentListRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  function handleJumpToVersionNumber(versionNumber: number, successMessage: string) {
    const targetVersion =
      versions.find((version) => version.version_number === versionNumber) ?? null;
    if (!targetVersion) {
      setError(`未找到 Version ${versionNumber} 的版本记录。`);
      return;
    }

    const previousVersion =
      [...versions]
        .filter((version) => version.version_number <= versionNumber)
        .sort((left, right) => right.version_number - left.version_number)[1] ??
      targetVersion;

    setCompareLeftVersionId(targetVersion.id);
    setCompareRightVersionId(previousVersion.id);
    setError(null);
    setSuccess(successMessage);
    window.requestAnimationFrame(() => {
      versionCompareRef.current?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  function handleJumpToCheckpointVersion(checkpoint: ChapterCheckpoint) {
    handleJumpToVersionNumber(
      checkpoint.chapter_version_number,
      `已定位到 Version ${checkpoint.chapter_version_number} 的版本上下文。`,
    );
  }

  function handleLocateCommentSelection(comment: ChapterReviewComment) {
    if (
      comment.selection_start === null ||
      comment.selection_end === null ||
      !contentRef.current
    ) {
      setError("这条批注没有正文选区锚点，无法直接定位。");
      return;
    }

    const textarea = contentRef.current;
    textarea.focus();
    textarea.setSelectionRange(comment.selection_start, comment.selection_end);
    const lineHeight = 32;
    const lineCount =
      textarea.value.slice(0, comment.selection_start).split("\n").length - 1;
    textarea.scrollTop = Math.max(0, lineCount * lineHeight - textarea.clientHeight / 3);
    setError(null);
    setSuccess("已定位到正文中的批注选区。");
  }

  function renderCommentCard(
    comment: ChapterReviewComment,
    options: { isReply: boolean },
  ) {
    const isReply = options.isReply;
    const isReplyComposerOpen = activeReplyCommentId === comment.id;
    const replyDraft = replyDrafts[comment.id] ?? "";
    const isUpdating = updatingCommentId === comment.id;
    const isReplySubmitting = submittingReplyToCommentId === comment.id;

    return (
      <article
        className={`rounded-2xl border border-black/10 p-3 ${
          isReply ? "bg-white/90" : "bg-white"
        }`}
      >
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs uppercase tracking-[0.16em] text-copper">
                {comment.author_email || "Unknown"}
              </p>
              <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-2 py-1 text-[11px] text-black/55">
                {isReply ? "回复" : "根批注"}
              </span>
              {!isReply && comment.reply_count > 0 ? (
                <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-2 py-1 text-[11px] text-black/55">
                  回复 {comment.reply_count}
                </span>
              ) : null}
            </div>
            <p className="mt-1 text-xs text-black/50">
              Version {comment.chapter_version_number}
              {" · "}
              {formatDateTime(comment.created_at)}
            </p>
          </div>
          <span
            className={`rounded-full border px-2 py-1 text-xs ${
              comment.status === "open"
                ? "border-amber-200 bg-amber-50 text-amber-700"
                : "border-emerald-200 bg-emerald-50 text-emerald-700"
            }`}
          >
            {comment.status === "open" ? "开放" : "已解决"}
          </span>
        </div>

        {comment.selection_text ? (
          <div className="mt-3 rounded-2xl border border-black/10 bg-[#fbfaf5] px-3 py-2">
            <p className="text-xs uppercase tracking-[0.16em] text-copper">
              引用片段
            </p>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-black/70">
              {comment.selection_text}
            </p>
          </div>
        ) : null}

        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-black/75">
          {comment.body}
        </p>

        {comment.resolved_at ? (
          <p className="mt-3 text-xs text-black/50">
            由 {comment.resolved_by_email || "Unknown"} 于{" "}
            {formatDateTime(comment.resolved_at)} 标记为已解决
          </p>
        ) : null}

        {!isReply && comment.reply_count > 0 && !comment.can_delete ? (
          <p className="mt-3 text-xs leading-6 text-black/50">
            当前线程已有回复，根批注需要先清空回复后才能删除。
          </p>
        ) : null}

        <div className="mt-3 flex flex-wrap gap-2">
          {comment.selection_start !== null && comment.selection_end !== null ? (
            <button
              className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-3 py-2 text-sm"
              type="button"
              onClick={() => handleLocateCommentSelection(comment)}
            >
              定位正文
            </button>
          ) : null}
          <button
            className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-3 py-2 text-sm"
            type="button"
            onClick={() =>
              handleJumpToVersionNumber(
                comment.chapter_version_number,
                `已定位到 Version ${comment.chapter_version_number} 的批注上下文。`,
              )
            }
          >
            版本上下文
          </button>
          {canComment ? (
            <button
              className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-3 py-2 text-sm"
              type="button"
              onClick={() => handleStartReply(comment.id)}
            >
              回复
            </button>
          ) : null}
          {comment.can_change_status ? (
            <button
              className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              onClick={() => void handleToggleCommentStatus(comment)}
              disabled={isUpdating}
            >
              {isUpdating
                ? "处理中..."
                : comment.status === "open"
                  ? "标记已解决"
                  : "重新打开"}
            </button>
          ) : null}
          {comment.can_delete ? (
            <button
              className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
              type="button"
              onClick={() => void handleDeleteComment(comment)}
              disabled={isUpdating}
            >
              删除
            </button>
          ) : null}
        </div>

        {isReplyComposerOpen ? (
          <div className="mt-3 rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
            <p className="text-xs uppercase tracking-[0.16em] text-copper">
              Thread Reply
            </p>
            <p className="mt-2 text-xs leading-6 text-black/55">
              {comment.parent_comment_id
                ? "这是对回复的回复，提交后会自动挂到当前线程的根批注下。"
                : "回复会挂到这条根批注下面。"}
            </p>
            <textarea
              className="mt-3 min-h-[110px] w-full rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none transition focus:border-copper"
              value={replyDraft}
              onChange={(event) =>
                setReplyDrafts((current) => ({
                  ...current,
                  [comment.id]: event.target.value,
                }))
              }
              disabled={!canComment}
              placeholder="补充解释、处理方案，或者继续追问这个问题。"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleCreateReply(comment)}
                disabled={isReplySubmitting || !canComment}
              >
                {isReplySubmitting ? "提交中..." : "发送回复"}
              </button>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={handleCancelReply}
                disabled={isReplySubmitting}
              >
                收起
              </button>
            </div>
          </div>
        ) : null}
      </article>
    );
  }

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <section className="rounded-3xl border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-copper">
                Editor
              </p>
              <h1 className="mt-3 text-4xl font-semibold">
                {chapter?.title || "章节编辑器"}
              </h1>
              <p className="mt-3 text-sm leading-7 text-black/65">
                当前已打通正文保存、版本回滚、生成任务、评估结果、协作审阅与任务时间线，侧边栏会持续显示后台执行痕迹。
              </p>
              {reviewWorkspace ? (
                <p className="mt-3 text-sm leading-7 text-black/55">
                  当前角色：{formatRoleLabel(reviewWorkspace.current_role)}
                  {reviewWorkspace.owner_email
                    ? ` · Owner ${reviewWorkspace.owner_email}`
                    : ""}
                </p>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href={chapter ? `/dashboard/projects/${chapter.project_id}/chapters` : "/dashboard"}
              >
                返回章节列表
              </Link>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleCreateGenerationTask()}
                disabled={startingTask || !canRunGeneration}
              >
                {startingTask ? "创建任务中..." : "创建生成任务"}
              </button>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleEvaluate()}
                disabled={evaluating || !canRunEvaluation}
              >
                {evaluating ? "评估中..." : "运行评估"}
              </button>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleExportChapter("md")}
                disabled={exportingFormat === "md"}
              >
                {exportingFormat === "md" ? "导出中..." : "导出章节 MD"}
              </button>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleExportChapter("txt")}
                disabled={exportingFormat === "txt"}
              >
                {exportingFormat === "txt" ? "导出中..." : "导出章节 TXT"}
              </button>
              <button
                className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                type="button"
                onClick={() => void handleSave()}
                disabled={saving || !canEditChapter}
              >
                {saving ? "保存中..." : "保存章节"}
              </button>
            </div>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.6fr_0.8fr]">
          <div className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            {loading ? (
              <p className="text-sm text-black/65">加载章节中...</p>
            ) : (
              <>
                <div className="grid gap-4 md:grid-cols-2">
                  <label className="flex flex-col gap-2 text-sm">
                    标题
                    <input
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      readOnly={!canEditChapter}
                    />
                  </label>
                  <label className="flex flex-col gap-2 text-sm">
                    状态
                    <select
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                      value={status}
                      onChange={(event) => setStatus(event.target.value)}
                      disabled={!canEditChapter}
                    >
                      <option value="draft">draft</option>
                      <option value="writing">writing</option>
                      <option value="review">review</option>
                      <option value="final">
                        {chapter?.final_ready ? "final" : "final (gate blocked)"}
                      </option>
                    </select>
                    {status === "final" && !chapter?.final_ready ? (
                      <p className="text-xs leading-6 text-red-700">
                        {buildFinalGateSaveError(chapter)}
                      </p>
                    ) : null}
                  </label>
                </div>

                {chapter ? (
                  <section
                    className={`mt-6 rounded-2xl border px-4 py-4 ${finalGateTone(
                      chapter.final_gate_status,
                    )}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.16em]">
                          Final Gate
                        </p>
                        <h2 className="mt-2 text-lg font-semibold">
                          {formatFinalGateStatus(chapter.final_gate_status)}
                        </h2>
                        <p className="mt-2 text-sm leading-7">
                          {buildFinalGateSummary(chapter)}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2 text-xs">
                        <span className="rounded-full border border-current/20 px-3 py-1">
                          Pending {chapter.pending_checkpoint_count}
                        </span>
                        <span className="rounded-full border border-current/20 px-3 py-1">
                          Rejected {chapter.rejected_checkpoint_count}
                        </span>
                        <span className="rounded-full border border-current/20 px-3 py-1">
                          {chapter.final_ready ? "Ready" : "Blocked"}
                        </span>
                      </div>
                    </div>

                    {chapter.latest_checkpoint_title ? (
                      <p className="mt-3 text-sm leading-7">
                        最近 checkpoint：{chapter.latest_checkpoint_title}
                        {chapter.latest_checkpoint_status
                          ? ` · ${formatCheckpointStatus(chapter.latest_checkpoint_status)}`
                          : ""}
                      </p>
                    ) : null}
                    {chapter.latest_review_verdict ? (
                      <div className="mt-3 rounded-2xl border border-current/20 bg-white/60 px-3 py-3 text-sm">
                        <p className="font-medium">
                          最新审阅：{formatReviewVerdict(chapter.latest_review_verdict)}
                        </p>
                        {chapter.latest_review_summary ? (
                          <p className="mt-2 leading-7">{chapter.latest_review_summary}</p>
                        ) : null}
                      </div>
                    ) : null}
                  </section>
                ) : null}

                <label className="mt-6 flex flex-col gap-2 text-sm">
                  Outline JSON
                  <textarea
                    className="min-h-[180px] rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 font-mono text-sm leading-7 outline-none transition focus:border-copper"
                    value={outlineText}
                    onChange={(event) => setOutlineText(event.target.value)}
                    readOnly={!canEditChapter}
                  />
                </label>

                <label className="mt-6 flex flex-col gap-2 text-sm">
                  正文
                  <textarea
                    ref={contentRef}
                    className="min-h-[520px] rounded-2xl border border-black/10 bg-white px-4 py-4 text-sm leading-8 outline-none transition focus:border-copper"
                    value={content}
                    onChange={(event) => setContent(event.target.value)}
                    readOnly={!canEditChapter}
                  />
                </label>

                <section className="mt-6 rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-lg font-semibold">局部重写</h2>
                      <p className="mt-2 text-sm leading-7 text-black/65">
                        选中正文中的一段，给出改写指令，系统会结合当前风格偏好和相关批注只重写这一段，并自动生成新版本。
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                        type="button"
                        onClick={captureRewriteAnchor}
                        disabled={!canEditChapter}
                      >
                        载入当前选区
                      </button>
                      {rewriteAnchor ? (
                        <button
                          className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                          type="button"
                          onClick={() => setRewriteAnchor(null)}
                        >
                          清除选区
                        </button>
                      ) : null}
                    </div>
                  </div>

                  {!canEditChapter ? (
                    <p className="mt-3 text-sm leading-7 text-amber-700">
                      当前角色不能直接发起局部重写。
                    </p>
                  ) : null}

                  {rewriteAnchor ? (
                    <div className="mt-4 rounded-2xl border border-black/10 bg-white p-4">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">
                        Rewrite Selection
                      </p>
                      <p className="mt-2 text-xs text-black/50">
                        {rewriteAnchor.selectionStart} - {rewriteAnchor.selectionEnd}
                      </p>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-black/75">
                        {rewriteAnchor.selectionText}
                      </p>
                    </div>
                  ) : (
                    <div className="mt-4 rounded-2xl border border-dashed border-black/10 bg-white/70 p-4 text-sm leading-7 text-black/60">
                      先在正文里选中需要改写的片段，再点击“载入当前选区”。
                    </div>
                  )}

                  <label className="mt-4 flex flex-col gap-2 text-sm">
                    改写指令
                    <textarea
                      className="min-h-[120px] rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none transition focus:border-copper"
                      value={rewriteInstruction}
                      onChange={(event) => setRewriteInstruction(event.target.value)}
                      disabled={!canEditChapter}
                      placeholder="例如：增强张力，压缩解释句，补一点身体反应，但不要改动事实。"
                    />
                  </label>

                  <button
                    className="mt-4 rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                    type="button"
                    onClick={() => void handleRewriteSelection()}
                    disabled={rewritingSelection || !canEditChapter || !rewriteAnchor}
                  >
                    {rewritingSelection ? "重写中..." : "执行局部重写"}
                  </button>

                  {lastRewriteResult ? (
                    <div className="mt-4 rounded-2xl border border-black/10 bg-white p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium">最近一次重写结果</p>
                          <p className="mt-2 text-sm leading-7 text-black/70">
                            指令：{lastRewriteResult.instruction}
                          </p>
                          <p className="mt-2 text-xs text-black/50">
                            Provider {lastRewriteResult.generation.provider}
                            {" · "}
                            {String(lastRewriteResult.generation.model)}
                            {" · "}
                            {lastRewriteResult.generation.used_fallback
                              ? "fallback"
                              : "remote"}
                            {" · "}
                            相关批注 {lastRewriteResult.related_comment_count}
                          </p>
                        </div>
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                          自动生成版本
                        </span>
                      </div>

                      <div className="mt-4 grid gap-3 lg:grid-cols-2">
                        <article className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                          <p className="text-xs uppercase tracking-[0.16em] text-copper">
                            Before
                          </p>
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-black/70">
                            {lastRewriteResult.original_text}
                          </p>
                        </article>
                        <article className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                          <p className="text-xs uppercase tracking-[0.16em] text-copper">
                            After
                          </p>
                          <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-black/70">
                            {lastRewriteResult.rewritten_text}
                          </p>
                        </article>
                      </div>
                    </div>
                  ) : null}
                </section>

                {!canEditChapter ? (
                  <p className="mt-4 text-sm leading-7 text-amber-700">
                    当前角色为只读审阅视图，不能直接改正文；其余审阅能力按当前角色权限开放。
                  </p>
                ) : null}

                <div className="mt-4 flex flex-wrap gap-4 text-sm text-black/60">
                  <span>章节号：{chapter?.chapter_number ?? "-"}</span>
                  <span>词数：{chapter?.word_count ?? 0}</span>
                  <span>版本数：{versions.length}</span>
                </div>

                {error ? (
                  <div className="mt-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                  </div>
                ) : null}

                {success ? (
                  <div className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                    {success}
                  </div>
                ) : null}
              </>
            )}
          </div>

          <aside className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">协作审阅</h2>
                  <p className="mt-2 text-sm leading-7 text-black/65">
                    这里承接批注、第三方审阅和人工确认，不直接替代正文编辑。
                  </p>
                </div>
                <button
                  className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                  type="button"
                  onClick={() =>
                    void Promise.all([
                      loadReviewWorkspace(),
                      refreshChapterStatusSnapshot(),
                    ])
                  }
                >
                  刷新审阅
                </button>
              </div>

              {reviewWorkspace ? (
                <div className="mt-4 grid gap-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-2xl border border-black/10 bg-white p-4">
                      <p className="text-sm text-black/60">开放批注</p>
                      <p className="mt-2 text-2xl font-semibold">
                        {reviewWorkspace.open_comment_count}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-white p-4">
                      <p className="text-sm text-black/60">已解决批注</p>
                      <p className="mt-2 text-2xl font-semibold">
                        {reviewWorkspace.resolved_comment_count}
                      </p>
                    </div>
                  </div>

                  {latestReviewDecision ? (
                    <article className="rounded-2xl border border-black/10 bg-white p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium">最新审阅结论</p>
                          <p className="mt-2 text-sm leading-7 text-black/70">
                            {latestReviewDecision.summary}
                          </p>
                          <p className="mt-2 text-xs text-black/50">
                            {latestReviewDecision.reviewer_email || "Unknown"}
                            {" · "}
                            Version {latestReviewDecision.chapter_version_number}
                            {" · "}
                            {formatDateTime(latestReviewDecision.created_at)}
                          </p>
                        </div>
                        <span
                          className={`rounded-full border px-3 py-1 text-xs ${reviewVerdictTone(
                            latestReviewDecision.verdict,
                          )}`}
                        >
                          {formatReviewVerdict(latestReviewDecision.verdict)}
                        </span>
                      </div>

                      {latestReviewDecision.focus_points.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {latestReviewDecision.focus_points.map((item) => (
                            <span
                              key={item}
                              className="rounded-full border border-black/10 bg-[#fbfaf5] px-2 py-1 text-xs text-black/60"
                            >
                              {item}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ) : (
                    <div className="rounded-2xl border border-dashed border-black/10 bg-white/70 p-4 text-sm leading-7 text-black/60">
                      还没有人工审阅结论。Reviewer / Editor / Owner 可以在这里记录通过、需修改或阻塞判断。
                    </div>
                  )}

                  <div className="rounded-2xl border border-black/10 bg-white p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium">关键节点确认</p>
                        <p className="mt-2 text-sm leading-7 text-black/65">
                          用来标记重要转折、大纲闸口或人工确认点，避免章节在关键节点上直接滑过去。
                        </p>
                      </div>
                      <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/60">
                        待确认 {reviewWorkspace.pending_checkpoint_count}
                      </span>
                    </div>

                    {latestPendingCheckpoint ? (
                      <article className="mt-4 rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-xs uppercase tracking-[0.16em] text-copper">
                              {formatCheckpointType(latestPendingCheckpoint.checkpoint_type)}
                            </p>
                            <p className="mt-2 text-sm font-medium text-black/80">
                              {latestPendingCheckpoint.title}
                            </p>
                            <p className="mt-2 text-xs text-black/50">
                              {latestPendingCheckpoint.requester_email || "Unknown"}
                              {" · "}
                              Version {latestPendingCheckpoint.chapter_version_number}
                            </p>
                          </div>
                          <span
                            className={`rounded-full border px-3 py-1 text-xs ${checkpointStatusTone(
                              latestPendingCheckpoint.status,
                            )}`}
                          >
                            {formatCheckpointStatus(latestPendingCheckpoint.status)}
                          </span>
                        </div>
                        {latestPendingCheckpoint.description ? (
                          <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-black/70">
                            {latestPendingCheckpoint.description}
                          </p>
                        ) : null}
                      </article>
                    ) : (
                      <div className="mt-4 rounded-2xl border border-dashed border-black/10 bg-white/70 p-4 text-sm leading-7 text-black/60">
                        当前没有待确认的关键节点。
                      </div>
                    )}

                    {!canRequestCheckpoint ? (
                      <p className="mt-3 text-sm leading-7 text-amber-700">
                        当前角色不能发起关键节点确认。
                      </p>
                    ) : null}

                    <div className="mt-4 grid gap-3">
                      <label className="flex flex-col gap-2 text-sm">
                        类型
                        <select
                          className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 outline-none"
                          value={checkpointType}
                          onChange={(event) => setCheckpointType(event.target.value)}
                          disabled={!canRequestCheckpoint}
                        >
                          <option value="story_turn">关键转折</option>
                          <option value="outline_gate">大纲关卡</option>
                          <option value="quality_gate">质量关卡</option>
                          <option value="branch_decision">分支决策</option>
                          <option value="manual_gate">人工确认</option>
                        </select>
                      </label>
                      <label className="flex flex-col gap-2 text-sm">
                        标题
                        <input
                          className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 outline-none"
                          value={checkpointTitle}
                          onChange={(event) => setCheckpointTitle(event.target.value)}
                          disabled={!canRequestCheckpoint}
                          placeholder="例如：主角是否正式暴露身份"
                        />
                      </label>
                      <label className="flex flex-col gap-2 text-sm">
                        说明
                        <textarea
                          className="min-h-[96px] rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 outline-none"
                          value={checkpointDescription}
                          onChange={(event) => setCheckpointDescription(event.target.value)}
                          disabled={!canRequestCheckpoint}
                          placeholder="说明这个节点为什么必须人工确认，确认标准是什么。"
                        />
                      </label>
                    </div>

                    <button
                      className="mt-4 rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                      type="button"
                      onClick={() => void handleCreateCheckpoint()}
                      disabled={submittingCheckpoint || !canRequestCheckpoint}
                    >
                      {submittingCheckpoint ? "提交中..." : "发起关键节点确认"}
                    </button>

                    {reviewCheckpoints.length > 0 ? (
                      <div className="mt-4 grid gap-3">
                        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                          <label className="flex flex-col gap-2 text-sm">
                            状态筛选
                            <select
                              className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none"
                              value={checkpointStatusFilter}
                              onChange={(event) =>
                                setCheckpointStatusFilter(event.target.value)
                              }
                            >
                              <option value="all">全部状态</option>
                              <option value="pending">待确认</option>
                              <option value="approved">已通过</option>
                              <option value="rejected">已驳回</option>
                              <option value="cancelled">已取消</option>
                            </select>
                          </label>
                          <label className="flex flex-col gap-2 text-sm">
                            类型筛选
                            <select
                              className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none"
                              value={checkpointTypeFilter}
                              onChange={(event) =>
                                setCheckpointTypeFilter(event.target.value)
                              }
                            >
                              <option value="all">全部类型</option>
                              <option value="story_turn">关键转折</option>
                              <option value="outline_gate">大纲关卡</option>
                              <option value="quality_gate">质量关卡</option>
                              <option value="branch_decision">分支决策</option>
                              <option value="manual_gate">人工确认</option>
                            </select>
                          </label>
                          <button
                            className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                            type="button"
                            onClick={() => {
                              setCheckpointStatusFilter("all");
                              setCheckpointTypeFilter("all");
                              setFocusedCheckpointId(null);
                            }}
                          >
                            清空筛选
                          </button>
                        </div>

                        {focusedCheckpoint ? (
                          <div className="rounded-2xl border border-copper/20 bg-[rgba(198,110,44,0.08)] p-3 text-sm text-black/75">
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <p className="font-medium">
                                  当前上下文：{focusedCheckpoint.title}
                                </p>
                                <p className="mt-1 leading-7">
                                  Version {focusedCheckpoint.chapter_version_number} · 关联批注{" "}
                                  {commentsByVersionNumber[
                                    focusedCheckpoint.chapter_version_number
                                  ] ?? 0}
                                </p>
                              </div>
                              <button
                                className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                                type="button"
                                onClick={() => setFocusedCheckpointId(null)}
                              >
                                清除上下文
                              </button>
                            </div>
                          </div>
                        ) : null}

                        {filteredCheckpoints.length === 0 ? (
                          <div className="rounded-2xl border border-dashed border-black/10 bg-white/70 p-4 text-sm leading-7 text-black/60">
                            当前筛选条件下没有 checkpoint 记录。
                          </div>
                        ) : (
                          filteredCheckpoints.map((checkpoint) => (
                          <article
                            key={checkpoint.id}
                            className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3"
                          >
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                  {formatCheckpointType(checkpoint.checkpoint_type)}
                                </p>
                                <p className="mt-2 text-sm font-medium text-black/80">
                                  {checkpoint.title}
                                </p>
                                <p className="mt-2 text-xs text-black/50">
                                  {checkpoint.requester_email || "Unknown"}
                                  {" · "}
                                  Version {checkpoint.chapter_version_number}
                                  {" · "}
                                  {formatDateTime(checkpoint.created_at)}
                                  {" · "}
                                  关联批注 {commentsByVersionNumber[checkpoint.chapter_version_number] ?? 0}
                                </p>
                              </div>
                              <span
                                className={`rounded-full border px-2 py-1 text-xs ${checkpointStatusTone(
                                  checkpoint.status,
                                )}`}
                              >
                                {formatCheckpointStatus(checkpoint.status)}
                              </span>
                            </div>

                            {checkpoint.description ? (
                              <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-black/70">
                                {checkpoint.description}
                              </p>
                            ) : null}

                            {checkpoint.decision_note ? (
                              <div className="mt-3 rounded-2xl border border-black/10 bg-white p-3">
                                <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                  决策说明
                                </p>
                                <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-black/70">
                                  {checkpoint.decision_note}
                                </p>
                                {checkpoint.decided_at ? (
                                  <p className="mt-2 text-xs text-black/50">
                                    {checkpoint.decided_by_email || "Unknown"}
                                    {" · "}
                                    {formatDateTime(checkpoint.decided_at)}
                                  </p>
                                ) : null}
                              </div>
                            ) : null}

                            <div className="mt-3 flex flex-wrap gap-2">
                              <button
                                className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                                type="button"
                                onClick={() => handleFocusCheckpointComments(checkpoint)}
                                disabled={
                                  (commentsByVersionNumber[checkpoint.chapter_version_number] ??
                                    0) === 0
                                }
                              >
                                查看关联批注
                              </button>
                              <button
                                className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                                type="button"
                                onClick={() => handleJumpToCheckpointVersion(checkpoint)}
                              >
                                版本上下文
                              </button>
                            </div>

                            {(checkpoint.can_decide || checkpoint.can_cancel) ? (
                              <div className="mt-3 flex flex-wrap gap-2">
                                {checkpoint.can_decide ? (
                                  <>
                                    <button
                                      className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                                      type="button"
                                      onClick={() =>
                                        void handleUpdateCheckpoint(checkpoint, "approved")
                                      }
                                      disabled={
                                        updatingCheckpointId === checkpoint.id ||
                                        !canDecideCheckpoint
                                      }
                                    >
                                      通过
                                    </button>
                                    <button
                                      className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                                      type="button"
                                      onClick={() =>
                                        void handleUpdateCheckpoint(checkpoint, "rejected")
                                      }
                                      disabled={
                                        updatingCheckpointId === checkpoint.id ||
                                        !canDecideCheckpoint
                                      }
                                    >
                                      驳回
                                    </button>
                                  </>
                                ) : null}
                                {checkpoint.can_cancel ? (
                                  <button
                                    className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                                    type="button"
                                    onClick={() =>
                                      void handleUpdateCheckpoint(checkpoint, "cancelled")
                                    }
                                    disabled={updatingCheckpointId === checkpoint.id}
                                  >
                                    取消
                                  </button>
                                ) : null}
                              </div>
                            ) : null}
                          </article>
                          ))
                        )}
                      </div>
                    ) : null}
                  </div>

                  {reviewTimelineItems.length > 0 ? (
                    <div className="rounded-2xl border border-black/10 bg-white p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium">审阅时间线</p>
                        <p className="text-xs text-black/45">
                          {reviewTimelineItems.length} items
                        </p>
                      </div>
                      <div className="mt-4 grid gap-3">
                        {reviewTimelineItems.slice(0, 14).map((item) => (
                          <article
                            key={`${item.itemType}-${item.id}`}
                            className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3"
                          >
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <p className="text-sm font-medium">{item.title}</p>
                                <p className="mt-1 text-xs text-black/50">
                                  {item.subtitle}
                                  {" · "}
                                  {formatDateTime(item.timestamp)}
                                </p>
                              </div>
                              <span
                                className={`rounded-full border px-2 py-1 text-xs ${item.toneClass}`}
                              >
                                {item.itemType === "comment"
                                  ? item.comment.status === "resolved"
                                    ? "resolved"
                                    : "open"
                                  : item.itemType === "decision"
                                    ? formatReviewVerdict(item.decision.verdict)
                                    : formatCheckpointStatus(item.checkpoint.status)}
                              </span>
                            </div>
                            <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-black/75">
                              {item.body}
                            </p>

                            <div className="mt-3 flex flex-wrap gap-2">
                              {item.itemType === "comment" ? (
                                <>
                                  {item.comment.selection_start !== null &&
                                  item.comment.selection_end !== null ? (
                                    <button
                                      className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                                      type="button"
                                      onClick={() =>
                                        handleLocateCommentSelection(item.comment)
                                      }
                                    >
                                      定位正文
                                    </button>
                                  ) : null}
                                  <button
                                    className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                                    type="button"
                                    onClick={() =>
                                      handleJumpToVersionNumber(
                                        item.comment.chapter_version_number,
                                        `已定位到 Version ${item.comment.chapter_version_number} 的批注上下文。`,
                                      )
                                    }
                                  >
                                    版本上下文
                                  </button>
                                </>
                              ) : null}

                              {item.itemType === "decision" ? (
                                <button
                                  className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                                  type="button"
                                  onClick={() =>
                                    handleJumpToVersionNumber(
                                      item.decision.chapter_version_number,
                                      `已定位到 Version ${item.decision.chapter_version_number} 的审阅结论上下文。`,
                                    )
                                  }
                                >
                                  版本上下文
                                </button>
                              ) : null}

                              {item.itemType === "checkpoint" ? (
                                <>
                                  <button
                                    className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                                    type="button"
                                    onClick={() =>
                                      handleFocusCheckpointComments(item.checkpoint)
                                    }
                                    disabled={
                                      (commentsByVersionNumber[
                                        item.checkpoint.chapter_version_number
                                      ] ?? 0) === 0
                                    }
                                  >
                                    查看关联批注
                                  </button>
                                  <button
                                    className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                                    type="button"
                                    onClick={() =>
                                      handleJumpToCheckpointVersion(item.checkpoint)
                                    }
                                  >
                                    版本上下文
                                  </button>
                                </>
                              ) : null}
                            </div>
                          </article>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <div className="rounded-2xl border border-black/10 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium">新增批注</p>
                        <p className="mt-1 text-xs text-black/50">
                          这里创建根批注；如果要继续讨论某条意见，请在对应批注下直接回复。
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                          type="button"
                          onClick={captureCommentAnchor}
                          disabled={!canComment}
                        >
                          引用当前选区
                        </button>
                        {commentAnchor ? (
                          <button
                            className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                            type="button"
                            onClick={() => setCommentAnchor(null)}
                          >
                            清除锚点
                          </button>
                        ) : null}
                      </div>
                    </div>

                    {!canComment ? (
                      <p className="mt-3 text-sm leading-7 text-amber-700">
                        当前角色不能创建批注，只能查看已有审阅结果。
                      </p>
                    ) : null}

                    {commentAnchor ? (
                      <div className="mt-3 rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                        <p className="text-xs uppercase tracking-[0.16em] text-copper">
                          Anchored Selection
                        </p>
                        <p className="mt-2 text-xs text-black/50">
                          {commentAnchor.selectionStart} - {commentAnchor.selectionEnd}
                        </p>
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-black/70">
                          {commentAnchor.selectionText}
                        </p>
                      </div>
                    ) : null}

                    <textarea
                      className="mt-4 min-h-[132px] w-full rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 outline-none transition focus:border-copper"
                      value={commentBody}
                      onChange={(event) => setCommentBody(event.target.value)}
                      disabled={!canComment}
                      placeholder="记录这一段的问题、建议动作或需要作者确认的点。"
                    />

                    <button
                      className="mt-4 rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                      type="button"
                      onClick={() => void handleCreateComment()}
                      disabled={submittingComment || !canComment}
                    >
                      {submittingComment ? "提交中..." : "添加批注"}
                    </button>
                  </div>

                  <div className="rounded-2xl border border-black/10 bg-white p-4">
                    <p className="text-sm font-medium">记录审阅结论</p>
                    {!canDecide ? (
                      <p className="mt-3 text-sm leading-7 text-amber-700">
                        当前角色不能提交审阅结论。
                      </p>
                    ) : null}
                    <div className="mt-4 grid gap-3">
                      <label className="flex flex-col gap-2 text-sm">
                        结论
                        <select
                          className="rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 outline-none"
                          value={decisionVerdict}
                          onChange={(event) => setDecisionVerdict(event.target.value)}
                          disabled={!canDecide}
                        >
                          <option value="changes_requested">需修改</option>
                          <option value="approved">通过</option>
                          <option value="blocked">阻塞</option>
                        </select>
                      </label>
                      <label className="flex flex-col gap-2 text-sm">
                        摘要
                        <textarea
                          className="min-h-[110px] rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 outline-none"
                          value={decisionSummary}
                          onChange={(event) => setDecisionSummary(event.target.value)}
                          disabled={!canDecide}
                        />
                      </label>
                      <label className="flex flex-col gap-2 text-sm">
                        关注点
                        <textarea
                          className="min-h-[96px] rounded-2xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 outline-none"
                          value={decisionFocusText}
                          onChange={(event) => setDecisionFocusText(event.target.value)}
                          disabled={!canDecide}
                          placeholder="可用逗号或换行分隔，例如：情绪承接，场景调度"
                        />
                      </label>
                    </div>

                    <button
                      className="mt-4 rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper disabled:cursor-not-allowed disabled:opacity-60"
                      type="button"
                      onClick={() => void handleCreateReviewDecision()}
                      disabled={submittingDecision || !canDecide}
                    >
                      {submittingDecision ? "提交中..." : "记录审阅结论"}
                    </button>
                  </div>

                  <div
                    ref={commentListRef}
                    className="rounded-2xl border border-black/10 bg-white p-4"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium">批注线程</p>
                      <p className="text-xs text-black/45">
                        {visibleCommentThreads.length} threads · {visibleCommentCount} comments
                      </p>
                    </div>

                    {focusedCheckpoint ? (
                      <div className="mt-3 rounded-2xl border border-copper/20 bg-[rgba(198,110,44,0.08)] p-3 text-sm text-black/75">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="font-medium">
                              正在查看 checkpoint「{focusedCheckpoint.title}」相关批注线程
                            </p>
                            <p className="mt-1 leading-7">
                              Version {focusedCheckpoint.chapter_version_number} 命中批注{" "}
                              {commentsByVersionNumber[
                                focusedCheckpoint.chapter_version_number
                              ] ?? 0}
                            </p>
                          </div>
                          <button
                            className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                            type="button"
                            onClick={() => setFocusedCheckpointId(null)}
                          >
                            显示全部批注
                          </button>
                        </div>
                      </div>
                    ) : null}

                    {reviewComments.length === 0 ? (
                      <p className="mt-3 text-sm leading-7 text-black/60">
                        当前还没有批注。先从正文中选中一段，再留下局部重写建议或审稿意见。
                      </p>
                    ) : visibleCommentThreads.length === 0 ? (
                      <p className="mt-3 text-sm leading-7 text-black/60">
                        当前 checkpoint 对应版本下还没有命中的批注线程。
                      </p>
                    ) : (
                      <div className="mt-4 grid gap-3">
                        {visibleCommentThreads.map((thread) => (
                          <div
                            key={thread.root.id}
                            className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-3"
                          >
                            {renderCommentCard(thread.root, { isReply: false })}
                            {thread.replies.length > 0 ? (
                              <div className="mt-3 ml-4 border-l border-black/10 pl-4">
                                <div className="grid gap-3">
                                  {thread.replies.map((reply) => (
                                    <div key={reply.id}>
                                      {renderCommentCard(reply, { isReply: true })}
                                    </div>
                                  ))}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {reviewDecisions.length > 0 ? (
                    <div className="rounded-2xl border border-black/10 bg-white p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium">审阅历史</p>
                        <p className="text-xs text-black/45">{reviewDecisions.length} entries</p>
                      </div>
                      <div className="mt-4 grid gap-3">
                        {reviewDecisions.map((decision) => (
                          <article
                            key={decision.id}
                            className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3"
                          >
                            <div className="flex flex-wrap items-start justify-between gap-3">
                              <div>
                                <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                  {decision.reviewer_email || "Unknown"}
                                </p>
                                <p className="mt-1 text-xs text-black/50">
                                  Version {decision.chapter_version_number}
                                  {" · "}
                                  {formatDateTime(decision.created_at)}
                                </p>
                              </div>
                              <span
                                className={`rounded-full border px-2 py-1 text-xs ${reviewVerdictTone(
                                  decision.verdict,
                                )}`}
                              >
                                {formatReviewVerdict(decision.verdict)}
                              </span>
                            </div>
                            <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-black/75">
                              {decision.summary}
                            </p>
                            {decision.focus_points.length > 0 ? (
                              <div className="mt-3 flex flex-wrap gap-2">
                                {decision.focus_points.map((item) => (
                                  <span
                                    key={`${decision.id}-${item}`}
                                    className="rounded-full border border-black/10 bg-white px-2 py-1 text-xs text-black/60"
                                  >
                                    {item}
                                  </span>
                                ))}
                              </div>
                            ) : null}
                          </article>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="mt-3 text-sm leading-7 text-black/60">
                  审阅工作区加载中...
                </p>
              )}
            </div>

            <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">任务状态</h2>
                <button
                  className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                  type="button"
                  onClick={() => void refreshTaskState()}
                  disabled={!taskState}
                >
                  刷新任务
                </button>
              </div>

              {!taskState ? (
                <p className="mt-3 text-sm leading-7 text-black/65">
                  当前还没有生成任务。创建后这里会持续展示实时状态和事件时间线。
                </p>
              ) : (
                <div className="mt-4 grid gap-3 text-sm text-black/70">
                  <p>Task ID: {taskState.task_id}</p>
                  <p>类型: {taskState.task_type}</p>
                  <p>状态: {taskState.status}</p>
                  <p>进度: {taskState.progress}%</p>
                  <p>消息: {taskState.message ?? "-"}</p>

                  <div className="rounded-2xl border border-black/10 bg-white p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-medium">任务时间线</p>
                      <p className="text-xs text-black/45">
                        {taskEvents.length}
                        {" "}
                        events
                      </p>
                    </div>

                    {taskEvents.length === 0 ? (
                      <p className="mt-3 text-sm leading-7 text-black/60">
                        时间线正在同步，下一次状态更新后会自动补齐。
                      </p>
                    ) : (
                      <div className="mt-3 grid gap-3">
                        {taskEvents.map((event) => {
                          const payloadSummary = summarizeTaskEventPayload(event.payload);

                          return (
                            <article
                              key={event.id}
                              className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3"
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                    {formatTaskEventLabel(event.event_type)}
                                  </p>
                                  <p className="mt-2 text-sm leading-7 text-black/75">
                                    {event.message ?? "-"}
                                  </p>
                                </div>
                                <div className="text-right text-xs text-black/45">
                                  <p>{formatDateTime(event.created_at)}</p>
                                  <p className="mt-1">{event.progress}%</p>
                                </div>
                              </div>

                              <div className="mt-3 flex flex-wrap gap-2 text-xs text-black/55">
                                <span className="rounded-full border border-black/10 bg-white px-2 py-1">
                                  {event.status}
                                </span>
                                {payloadSummary.map((item) => (
                                  <span
                                    key={`${event.id}-${item}`}
                                    className="rounded-full border border-black/10 bg-white px-2 py-1"
                                  >
                                    {item}
                                  </span>
                                ))}
                              </div>
                            </article>
                          );
                        })}
                      </div>
                    )}
                  </div>

                  {taskState.result?.evaluation ? (
                    <div className="rounded-2xl border border-black/10 bg-white p-3">
                      <p className="text-sm font-medium">任务内评估摘要</p>
                      <p className="mt-2 text-sm">
                        综合评分：
                        {(
                          Number(
                            (
                              taskState.result.evaluation as Record<string, unknown>
                            ).overall_score ?? 0,
                          ) * 10
                        ).toFixed(1)}
                        /10
                      </p>
                      <p className="mt-1 text-sm">
                        AI 味：
                        {Number(
                          (
                            taskState.result.evaluation as Record<string, unknown>
                          ).ai_taste_score ?? 0,
                        ).toFixed(2)}
                      </p>
                    </div>
                  ) : null}

                  {typeof taskState.result?.revised === "boolean" ? (
                    <p>
                      是否触发修订：
                      {taskState.result.revised ? "是" : "否"}
                    </p>
                  ) : null}

                  {typeof taskState.result?.chapter_status === "string" ? (
                    <p>
                      章节状态落位：
                      {String(taskState.result.chapter_status)}
                    </p>
                  ) : null}

                  {Array.isArray(taskState.result?.agent_trace) &&
                  taskState.result.agent_trace.length > 0 ? (
                    <div className="rounded-2xl border border-black/10 bg-white p-3">
                      <p className="text-sm font-medium">Agent Trace</p>
                      <div className="mt-3 grid gap-3">
                        {taskState.result.agent_trace
                          .slice(0, 6)
                          .map((item, index) => {
                            const trace = item as Record<string, unknown>;
                            return (
                              <article
                                key={`${String(trace.agent)}-${index}`}
                                className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3"
                              >
                                <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                  {String(trace.agent)}
                                </p>
                                <p className="mt-2 text-sm leading-7 text-black/70">
                                  {String(trace.reasoning ?? "")}
                                </p>
                                {trace.data ? (
                                  <pre className="mt-3 overflow-x-auto rounded-2xl bg-white p-3 text-xs leading-6 text-black/65">
                                    {JSON.stringify(trace.data, null, 2)}
                                  </pre>
                                ) : null}
                              </article>
                            );
                          })}
                      </div>
                    </div>
                  ) : null}

                  {taskState.result?.context_bundle ? (
                    <div className="rounded-2xl border border-black/10 bg-white p-3">
                      <p className="text-sm font-medium">检索上下文</p>
                      <p className="mt-2 text-sm text-black/70">
                        Query:
                        {" "}
                        {String(
                          (
                            taskState.result.context_bundle as Record<string, unknown>
                          ).query ?? "-",
                        )}
                      </p>
                      <p className="mt-1 text-sm text-black/70">
                        Retrieved:
                        {" "}
                        {Array.isArray(
                          (
                            taskState.result.context_bundle as Record<string, unknown>
                          ).retrieved_items,
                        )
                          ? (
                              (
                                taskState.result.context_bundle as Record<string, unknown>
                              ).retrieved_items as unknown[]
                            ).length
                          : 0}
                      </p>
                      <p className="mt-1 text-sm text-black/70">
                        Backends:
                        {" "}
                        {Array.isArray(
                          (
                            taskState.result.context_bundle as Record<string, unknown>
                          ).retrieval_backends,
                        )
                          ? (
                              (
                                taskState.result.context_bundle as Record<string, unknown>
                              ).retrieval_backends as unknown[]
                            ).join(", ")
                          : "lexical"}
                      </p>
                    </div>
                  ) : null}

                  {taskInitialReview || taskFinalReview ? (
                    <div className="rounded-2xl border border-black/10 bg-white p-3">
                      <p className="text-sm font-medium">审校回路</p>
                      <div className="mt-3 grid gap-3 md:grid-cols-2">
                        {taskInitialReview ? (
                          <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                            <p className="text-xs uppercase tracking-[0.16em] text-copper">
                              初评
                            </p>
                            <p className="mt-2 text-sm text-black/70">
                              综合评分：
                              {" "}
                              {(Number(taskInitialReview.overall_score ?? 0) * 10).toFixed(1)}
                              /10
                            </p>
                            <p className="mt-1 text-sm text-black/70">
                              是否建议修订：
                              {" "}
                              {taskInitialReview.needs_revision ? "是" : "否"}
                            </p>
                            <p className="mt-1 text-sm text-black/70">
                              问题数：
                              {" "}
                              {Array.isArray(taskInitialReview.issues)
                                ? taskInitialReview.issues.length
                                : 0}
                            </p>
                          </div>
                        ) : null}
                        {taskFinalReview ? (
                          <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                            <p className="text-xs uppercase tracking-[0.16em] text-copper">
                              复评
                            </p>
                            <p className="mt-2 text-sm text-black/70">
                              综合评分：
                              {" "}
                              {(Number(taskFinalReview.overall_score ?? 0) * 10).toFixed(1)}
                              /10
                            </p>
                            <p className="mt-1 text-sm text-black/70">
                              是否仍需修订：
                              {" "}
                              {taskFinalReview.needs_revision ? "是" : "否"}
                            </p>
                            <p className="mt-1 text-sm text-black/70">
                              问题数：
                              {" "}
                              {Array.isArray(taskFinalReview.issues)
                                ? taskFinalReview.issues.length
                                : 0}
                            </p>
                          </div>
                        ) : null}
                      </div>

                      {taskRevisionFocus.length > 0 ? (
                        <div className="mt-3">
                          <p className="text-sm font-medium">修订焦点</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {taskRevisionFocus.slice(0, 6).map((item, index) => (
                              <span
                                key={`${String(item.dimension)}-${index}`}
                                className={`rounded-full border px-2 py-1 text-xs ${severityTone(
                                  String(item.severity ?? "low"),
                                )}`}
                              >
                                {String(item.dimension ?? "issue")}
                              </span>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      {taskDebateSummary ? (
                        <div className="mt-3 rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                          <p className="text-sm font-medium">辩论结论</p>
                          <p className="mt-2 text-sm leading-7 text-black/70">
                            {String(taskDebateSummary.summary ?? "")}
                          </p>
                          <div className="mt-3 grid gap-3 md:grid-cols-3">
                            <div className="rounded-2xl border border-black/10 bg-white p-3">
                              <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                Architect
                              </p>
                              <p className="mt-2 text-sm leading-7 text-black/70">
                                {String(taskDebateSummary.architect_position ?? "-")}
                              </p>
                            </div>
                            <div className="rounded-2xl border border-black/10 bg-white p-3">
                              <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                Critic
                              </p>
                              <p className="mt-2 text-sm leading-7 text-black/70">
                                {String(taskDebateSummary.critic_position ?? "-")}
                              </p>
                            </div>
                            <div className="rounded-2xl border border-black/10 bg-white p-3">
                              <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                Resolution
                              </p>
                              <p className="mt-2 text-sm leading-7 text-black/70">
                                {String(taskDebateSummary.resolution ?? "-")}
                              </p>
                            </div>
                          </div>
                        </div>
                      ) : null}

                      {taskRevisionPlan ? (
                        <div className="mt-3 rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                          <p className="text-sm font-medium">修订计划</p>
                          <p className="mt-2 text-sm text-black/70">
                            本章目标：
                            {" "}
                            {String(taskRevisionPlan.objective ?? "-")}
                          </p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {Array.isArray(taskRevisionPlan.focus_dimensions)
                              ? (
                                  taskRevisionPlan.focus_dimensions as unknown[]
                                ).map((item, index) => (
                                  <span
                                    key={`${String(item)}-${index}`}
                                    className="rounded-full border border-black/10 bg-white px-2 py-1 text-xs text-black/60"
                                  >
                                    {String(item)}
                                  </span>
                                ))
                              : null}
                          </div>

                          {Array.isArray(taskRevisionPlan.priorities) ? (
                            <div className="mt-3 grid gap-3">
                              {(taskRevisionPlan.priorities as Record<string, unknown>[])
                                .slice(0, 4)
                                .map((priority, index) => (
                                  <article
                                    key={`${String(priority.dimension)}-${index}`}
                                    className="rounded-2xl border border-black/10 bg-white p-3"
                                  >
                                    <div className="flex items-center justify-between gap-3">
                                      <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                        {String(priority.dimension ?? "issue")}
                                      </p>
                                      <span
                                        className={`rounded-full border px-2 py-1 text-xs ${severityTone(
                                          String(priority.severity ?? "low"),
                                        )}`}
                                      >
                                        {String(priority.severity ?? "low")}
                                      </span>
                                    </div>
                                    <p className="mt-2 text-sm leading-7 text-black/70">
                                      {String(priority.problem ?? "")}
                                    </p>
                                    <p className="mt-2 text-sm leading-7 text-black/70">
                                      动作：
                                      {" "}
                                      {String(priority.action ?? "-")}
                                    </p>
                                    <p className="mt-2 text-sm leading-7 text-black/55">
                                      验收：
                                      {" "}
                                      {String(priority.acceptance_criteria ?? "-")}
                                    </p>
                                  </article>
                                ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}

                      {taskApproval ? (
                        <div className="mt-3 rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <p className="text-sm font-medium">终审结论</p>
                              <p className="mt-2 text-sm leading-7 text-black/70">
                                {String(taskApproval.summary ?? "终审结果已生成。")}
                              </p>
                            </div>
                            <span
                              className={`rounded-full border px-3 py-1 text-xs ${approvalTone(
                                Boolean(taskApproval.approved),
                              )}`}
                            >
                              {taskApproval.approved ? "已通过" : "待修订"}
                            </span>
                          </div>

                          <div className="mt-3 grid gap-3 md:grid-cols-2">
                            <div className="rounded-2xl border border-black/10 bg-white p-3">
                              <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                流转建议
                              </p>
                              <p className="mt-2 text-sm leading-7 text-black/70">
                                {String(taskApproval.release_recommendation ?? "-")}
                              </p>
                            </div>
                            <div className="rounded-2xl border border-black/10 bg-white p-3">
                              <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                评分变化
                              </p>
                              <p className="mt-2 text-sm leading-7 text-black/70">
                                {Number(taskApproval.score_delta ?? 0).toFixed(2)}
                              </p>
                            </div>
                            <div className="rounded-2xl border border-black/10 bg-white p-3">
                              <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                终审评分
                              </p>
                              <p className="mt-2 text-sm leading-7 text-black/70">
                                {(Number(taskApproval.final_score ?? 0) * 10).toFixed(1)}
                                /10
                              </p>
                            </div>
                            <div className="rounded-2xl border border-black/10 bg-white p-3">
                              <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                阻塞问题
                              </p>
                              <p className="mt-2 text-sm leading-7 text-black/70">
                                {Array.isArray(taskApproval.blocking_issues)
                                  ? taskApproval.blocking_issues.length
                                  : 0}
                              </p>
                            </div>
                          </div>

                          {Array.isArray(taskApproval.blocking_issues) &&
                          taskApproval.blocking_issues.length > 0 ? (
                            <div className="mt-3 grid gap-3">
                              {(taskApproval.blocking_issues as Record<string, unknown>[])
                                .slice(0, 4)
                                .map((issue, index) => (
                                  <article
                                    key={`${String(issue.dimension)}-${index}`}
                                    className="rounded-2xl border border-black/10 bg-white p-3"
                                  >
                                    <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                      {String(issue.severity ?? "high")}
                                      {" / "}
                                      {String(issue.dimension ?? "issue")}
                                    </p>
                                    <p className="mt-2 text-sm leading-7 text-black/70">
                                      {String(issue.message ?? "")}
                                    </p>
                                  </article>
                                ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}

                      {Array.isArray(taskFinalReview?.issues) && taskFinalReview.issues.length > 0 ? (
                        <div className="mt-3 grid gap-3">
                          {(taskFinalReview.issues as Record<string, unknown>[])
                            .slice(0, 4)
                            .map((issue, index) => (
                              <article
                                key={`${String(issue.dimension)}-${index}`}
                                className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3"
                              >
                                <p className="text-xs uppercase tracking-[0.16em] text-copper">
                                  {String(issue.severity ?? "low")}
                                  {" / "}
                                  {String(issue.dimension ?? "issue")}
                                </p>
                                <p className="mt-2 text-sm leading-7 text-black/70">
                                  {String(issue.message ?? "")}
                                </p>
                              </article>
                            ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              )}
            </div>

            <div className="mt-6 rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
              <h2 className="text-lg font-semibold">质量评估</h2>

              {!evaluationReport ? (
                <p className="mt-3 text-sm leading-7 text-black/65">
                  当前还没有评估结果。运行评估后，这里会展示综合评分、AI 味和问题列表。
                </p>
              ) : (
                <div className="mt-4 grid gap-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-2xl border border-black/10 bg-white p-4">
                      <p className="text-sm text-black/60">综合评分</p>
                      <p className="mt-2 text-2xl font-semibold">
                        {(evaluationReport.overall_score * 10).toFixed(1)}/10
                      </p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-white p-4">
                      <p className="text-sm text-black/60">AI 味</p>
                      <p className="mt-2 text-2xl font-semibold">
                        {evaluationReport.ai_taste_score.toFixed(2)}
                      </p>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-black/10 bg-white p-4">
                    <p className="text-sm font-medium">评估总结</p>
                    <p className="mt-2 text-sm leading-7 text-black/70">
                      {evaluationReport.summary}
                    </p>
                  </div>

                  <div className="rounded-2xl border border-black/10 bg-white p-4">
                    <p className="text-sm font-medium">关键指标</p>
                    <div className="mt-3 grid gap-2 text-sm text-black/70">
                      {Object.entries(evaluationReport.metrics)
                        .slice(0, 8)
                        .map(([key, value]) => (
                          <div
                            key={key}
                            className="flex items-center justify-between gap-3"
                          >
                            <span>{formatMetricLabel(key)}</span>
                            <span>{value.toFixed(2)}</span>
                          </div>
                        ))}
                    </div>
                  </div>

                  <div className="rounded-2xl border border-black/10 bg-white p-4">
                    <p className="text-sm font-medium">问题列表</p>
                    {evaluationReport.issues.length === 0 ? (
                      <p className="mt-2 text-sm leading-7 text-black/65">
                        暂未发现结构化问题。
                      </p>
                    ) : (
                      <div className="mt-3 grid gap-3">
                        {evaluationReport.issues.map((issue, index) => (
                          <article
                            key={`${issue.dimension}-${index}`}
                            className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3"
                          >
                            <p className="text-xs uppercase tracking-[0.16em] text-copper">
                              {issue.severity} / {issue.dimension}
                            </p>
                            <p className="mt-2 text-sm leading-7 text-black/70">
                              {issue.message}
                            </p>
                          </article>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between">
              <h2 className="mt-6 text-xl font-semibold">版本历史</h2>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
                type="button"
                onClick={() => void loadEditor()}
              >
                刷新
              </button>
            </div>

            <div className="mt-6 grid gap-4">
              {versions.map((version) => (
                <article
                  key={version.id}
                  className="rounded-2xl border border-black/10 bg-white/80 p-4"
                >
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">
                    Version {version.version_number}
                  </p>
                  <p className="mt-2 text-sm leading-7 text-black/65">
                    {version.change_reason || "No change reason"}
                  </p>
                  <p className="mt-3 line-clamp-4 whitespace-pre-wrap text-sm text-black/70">
                    {version.content.slice(0, 280)}
                  </p>
                  <button
                    className="mt-4 rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                    type="button"
                    onClick={() => void handleRollback(version.id)}
                    disabled={rollingBack === version.id}
                  >
                    {rollingBack === version.id ? "回滚中..." : "回滚到此版本"}
                  </button>
                </article>
              ))}
            </div>

            {versions.length > 0 ? (
              <section
                ref={versionCompareRef}
                className="mt-6 rounded-2xl border border-black/10 bg-[#fbfaf5] p-4"
              >
                <h2 className="text-lg font-semibold">版本对比</h2>
                <div className="mt-4 grid gap-3 md:grid-cols-2">
                  <label className="flex flex-col gap-2 text-sm">
                    左侧版本
                    <select
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none"
                      value={compareLeftVersionId}
                      onChange={(event) => setCompareLeftVersionId(event.target.value)}
                    >
                      {versions.map((version) => (
                        <option key={version.id} value={version.id}>
                          Version {version.version_number}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-2 text-sm">
                    右侧版本
                    <select
                      className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none"
                      value={compareRightVersionId}
                      onChange={(event) => setCompareRightVersionId(event.target.value)}
                    >
                      {versions.map((version) => (
                        <option key={version.id} value={version.id}>
                          Version {version.version_number}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <div className="mt-4 flex flex-wrap gap-4 text-sm text-black/65">
                  <span>词数变化：{compareDeltaWords >= 0 ? `+${compareDeltaWords}` : compareDeltaWords}</span>
                  <span>字符变化：{compareDeltaChars >= 0 ? `+${compareDeltaChars}` : compareDeltaChars}</span>
                </div>

                <div className="mt-4 grid gap-4 xl:grid-cols-2">
                  <div className="rounded-2xl border border-black/10 bg-white p-4">
                    <p className="text-sm font-medium">
                      {compareLeftVersion
                        ? `Version ${compareLeftVersion.version_number}`
                        : "未选择"}
                    </p>
                    <p className="mt-2 text-xs uppercase tracking-[0.16em] text-copper">
                      {compareLeftVersion?.change_reason || "No change reason"}
                    </p>
                    <pre className="mt-4 max-h-[320px] overflow-auto whitespace-pre-wrap text-xs leading-6 text-black/70">
                      {compareLeftVersion?.content || ""}
                    </pre>
                  </div>

                  <div className="rounded-2xl border border-black/10 bg-white p-4">
                    <p className="text-sm font-medium">
                      {compareRightVersion
                        ? `Version ${compareRightVersion.version_number}`
                        : "未选择"}
                    </p>
                    <p className="mt-2 text-xs uppercase tracking-[0.16em] text-copper">
                      {compareRightVersion?.change_reason || "No change reason"}
                    </p>
                    <pre className="mt-4 max-h-[320px] overflow-auto whitespace-pre-wrap text-xs leading-6 text-black/70">
                      {compareRightVersion?.content || ""}
                    </pre>
                  </div>
                </div>
              </section>
            ) : null}
          </aside>
        </section>
      </div>
    </main>
  );
}
