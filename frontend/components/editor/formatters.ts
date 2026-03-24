import type { ChapterCheckpoint, ChapterReviewComment, ChapterReviewDecision } from "@/types/api";

export interface CommentAnchor {
  selectionEnd: number;
  selectionStart: number;
  selectionText: string;
}

export interface ReviewCommentThread {
  root: ChapterReviewComment;
  replies: ChapterReviewComment[];
}

export type ReviewTimelineItem =
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

export function buildReviewCommentThreads(
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

export function formatCommentTimelineTitle(comment: ChapterReviewComment): string {
  if (comment.parent_comment_id) {
    return comment.status === "resolved" ? "回复已解决" : "新增回复";
  }
  return comment.status === "resolved" ? "批注已解决" : "新增批注";
}

export function formatDateTime(value: string): string {
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

export function prettyJson(value: Record<string, unknown> | null): string {
  return value ? JSON.stringify(value, null, 2) : "";
}

export function countWords(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) {
    return 0;
  }
  return trimmed.split(/\s+/).length;
}

export function formatTaskEventLabel(eventType: string): string {
  const labels: Record<string, string> = {
    queued: "任务排队",
    dispatched: "任务分发",
    started: "开始执行",
    payload_built: "上下文装载",
    generation_started: "Agent 生成",
    outputs_persisting: "落库与评估",
    succeeded: "任务完成",
    failed: "任务失败",
  };
  return labels[eventType] ?? eventType.replace(/_/g, " ");
}

export function summarizeTaskEventPayload(payload: Record<string, unknown> | null): string[] {
  if (!payload) {
    return [];
  }
  const summary: string[] = [];
  if (typeof payload.phase === "string") {
    summary.push(`阶段 ${payload.phase}`);
  }
  if (typeof payload.dispatch_strategy === "string") {
    summary.push(
      payload.dispatch_strategy === "celery" ? "Celery Worker" : "本地回退",
    );
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
  if (typeof payload.truth_layer_status === "string") {
    summary.push(`Truth ${payload.truth_layer_status}`);
  }
  if (typeof payload.integrity_blocking_issue_count === "number") {
    summary.push(`Truth阻断 ${payload.integrity_blocking_issue_count}`);
  } else if (typeof payload.integrity_issue_count === "number") {
    summary.push(`Truth ${payload.integrity_issue_count}`);
  }
  if (Array.isArray(payload.revision_focus_dimensions) && payload.revision_focus_dimensions.length > 0) {
    summary.push(`聚焦 ${payload.revision_focus_dimensions.slice(0, 2).join(", ")}`);
  }
  if (typeof payload.ai_taste_score === "number") {
    summary.push(`机械感 ${payload.ai_taste_score.toFixed(2)}`);
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
    const shortenedQuery = payload.query.length > 36 ? `${payload.query.slice(0, 36)}...` : payload.query;
    summary.push(`Query ${shortenedQuery}`);
  }
  return summary.slice(0, 4);
}

export function formatMetricLabel(key: string): string {
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
    ai_taste_score: "机械感",
  };
  return labels[key] ?? key;
}

export function severityTone(severity: string): string {
  if (severity === "high") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (severity === "medium") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

export function approvalTone(approved: boolean): string {
  if (approved) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  return "border-amber-200 bg-amber-50 text-amber-700";
}

export function reviewVerdictTone(verdict: string): string {
  if (verdict === "approved") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (verdict === "blocked") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  return "border-amber-200 bg-amber-50 text-amber-700";
}

export function formatReviewVerdict(verdict: string): string {
  const labels: Record<string, string> = {
    approved: "已通过",
    changes_requested: "需修改",
    blocked: "阻塞",
  };
  return labels[verdict] ?? verdict;
}

export function formatRoleLabel(role: string): string {
  const labels: Record<string, string> = {
    owner: "Owner",
    editor: "Editor",
    reviewer: "Reviewer",
    viewer: "Viewer",
  };
  return labels[role] ?? role;
}

export function checkpointStatusTone(status: string): string {
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

export function formatCheckpointStatus(status: string): string {
  const labels: Record<string, string> = {
    pending: "待确认",
    approved: "已通过",
    rejected: "已驳回",
    cancelled: "已取消",
  };
  return labels[status] ?? status;
}

export function formatCheckpointType(type: string): string {
  const labels: Record<string, string> = {
    story_turn: "关键转折",
    outline_gate: "大纲关卡",
    quality_gate: "质量关卡",
    branch_decision: "分支决策",
    manual_gate: "人工确认",
  };
  return labels[type] ?? type;
}

export function reviewTimelineTone(kind: "comment" | "decision" | "checkpoint", status: string): string {
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

export function finalGateTone(status: string): string {
  if (status === "blocked_rejected") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "blocked_checkpoint") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (status === "blocked_review") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "blocked_evaluation") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (status === "blocked_integrity") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "blocked_canon") {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (status === "blocked_pending") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

export function formatFinalGateStatus(status: string): string {
  const labels: Record<string, string> = {
    ready: "可放行",
    blocked_pending: "待确认",
    blocked_rejected: "被驳回",
    blocked_checkpoint: "确认需重审",
    blocked_review: "复核未通过",
    blocked_evaluation: "检查需重跑",
    blocked_integrity: "设定圣经未通过",
    blocked_canon: "连续性未通过",
  };
  return labels[status] ?? status;
}

export function buildFinalGateSummary(chapter: {
  final_gate_status?: string;
  rejected_checkpoint_count?: number;
  pending_checkpoint_count?: number;
  latest_review_verdict?: string | null;
  latest_checkpoint_title?: string | null;
  latest_evaluation_stale_reason?: string | null;
  latest_story_bible_integrity_blocking_issue_count?: number;
  latest_story_bible_integrity_summary?: string | null;
  latest_canon_blocking_issue_count?: number;
  latest_canon_summary?: string | null;
  final_gate_reason?: string | null;
} | null): string {
  if (!chapter) {
    return "正在同步审批门禁状态。";
  }
  if (chapter.final_gate_status === "blocked_rejected") {
    return `当前有 ${chapter.rejected_checkpoint_count} 个被驳回的确认点，这章还不能收终稿。`;
  }
  if (chapter.final_gate_status === "blocked_pending") {
    return `当前还有 ${chapter.pending_checkpoint_count} 个待确认点，这章还不能收终稿。`;
  }
  if (chapter.final_gate_status === "blocked_review") {
    if (chapter.latest_review_verdict === "blocked") {
      return "最新人工复核结论仍然拦截，这章还不能收终稿。";
    }
    return "最新人工复核结论仍要求修改，这章还不能收终稿。";
  }
  if (chapter.final_gate_status === "blocked_checkpoint") {
    return chapter.final_gate_reason ?? "当前确认点对应的是旧版本，收终稿前需要重新确认。";
  }
  if (chapter.final_gate_status === "blocked_evaluation") {
    if (chapter.latest_evaluation_stale_reason) {
      return chapter.latest_evaluation_stale_reason;
    }
    return "当前章节缺少最新检查结果，收终稿前需要重新跑一轮检查。";
  }
  if (chapter.final_gate_status === "blocked_integrity") {
    const count = chapter.latest_story_bible_integrity_blocking_issue_count ?? 0;
    if (chapter.latest_story_bible_integrity_summary) {
      return chapter.latest_story_bible_integrity_summary;
    }
    return `当前设定圣经里还有 ${count} 个阻断问题，必须先修平基座设定后才能收终稿。`;
  }
  if (chapter.final_gate_status === "blocked_canon") {
    const count = chapter.latest_canon_blocking_issue_count ?? 0;
    if (chapter.latest_canon_summary) {
      return chapter.latest_canon_summary;
    }
    return `当前还有 ${count} 个阻断级连续性问题，这章还不能收终稿。`;
  }
  if (chapter.latest_checkpoint_title) {
    return "所有确认点已经闭环，当前可以进入终稿状态。";
  }
  return chapter.final_gate_reason ?? "当前没有待确认点阻塞终稿状态。";
}

export function buildFinalGateSaveError(chapter: {
  final_gate_status?: string;
  rejected_checkpoint_count?: number;
  pending_checkpoint_count?: number;
  latest_review_verdict?: string | null;
  latest_checkpoint_title?: string | null;
  latest_evaluation_stale_reason?: string | null;
  latest_story_bible_integrity_blocking_issue_count?: number;
  latest_story_bible_integrity_summary?: string | null;
  latest_canon_blocking_issue_count?: number;
  latest_canon_summary?: string | null;
  final_gate_reason?: string | null;
} | null): string {
  if (!chapter) {
    return "这一章的终稿状态还没同步完成，暂时不能收终稿。";
  }
  return chapter.final_gate_reason ?? buildFinalGateSummary(chapter);
}
