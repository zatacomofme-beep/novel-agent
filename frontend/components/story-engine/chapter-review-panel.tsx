"use client";

import { useEffect, useMemo, useState, type RefObject } from "react";

import {
  buildReviewCommentThreads,
  checkpointStatusTone,
  formatCheckpointStatus,
  formatCheckpointType,
  formatDateTime,
  formatReviewVerdict,
  reviewVerdictTone,
} from "@/components/editor/formatters";
import type {
  Chapter,
  ChapterReviewWorkspace,
  ChapterSelectionRewriteResponse,
  ChapterVersion,
} from "@/types/api";

type CommentCreatePayload = {
  body: string;
  parent_comment_id?: string | null;
  assignee_user_id?: string | null;
  selection_start?: number | null;
  selection_end?: number | null;
  selection_text?: string | null;
};

type CommentUpdatePayload = {
  status?: string;
  assignee_user_id?: string | null;
};

type CheckpointCreatePayload = {
  checkpoint_type: string;
  title: string;
  description?: string | null;
};

type CheckpointUpdatePayload = {
  status: string;
  decision_note?: string | null;
};

type ReviewDecisionCreatePayload = {
  verdict: string;
  summary: string;
  focus_points: string[];
};

type SelectionSnapshot = {
  start: number | null;
  end: number | null;
  text: string;
};

type ChapterReviewPanelProps = {
  activeChapter: Chapter | null;
  draftText: string;
  draftDirty: boolean;
  reviewWorkspace: ChapterReviewWorkspace | null;
  chapterVersions: ChapterVersion[];
  loading: boolean;
  submittingActionKey: string | null;
  editorTextareaRef: RefObject<HTMLTextAreaElement | null>;
  onCreateComment: (payload: CommentCreatePayload) => Promise<boolean>;
  onUpdateComment: (commentId: string, payload: CommentUpdatePayload) => Promise<boolean>;
  onDeleteComment: (commentId: string) => Promise<boolean>;
  onCreateCheckpoint: (payload: CheckpointCreatePayload) => Promise<boolean>;
  onUpdateCheckpoint: (checkpointId: string, payload: CheckpointUpdatePayload) => Promise<boolean>;
  onCreateDecision: (payload: ReviewDecisionCreatePayload) => Promise<boolean>;
  onRollback: (versionId: string, versionNumber: number) => Promise<boolean>;
  onRewriteSelection: (payload: {
    selection_start: number;
    selection_end: number;
    instruction: string;
  }) => Promise<ChapterSelectionRewriteResponse | null>;
};

const COMMENT_STATUS_OPTIONS = [
  { value: "open", label: "继续盯" },
  { value: "in_progress", label: "处理中" },
  { value: "resolved", label: "已解决" },
] as const;

const CHECKPOINT_TYPE_OPTIONS = [
  { value: "story_turn", label: "关键转折" },
  { value: "outline_gate", label: "大纲关卡" },
  { value: "quality_gate", label: "质量关卡" },
  { value: "branch_decision", label: "分支决策" },
  { value: "manual_gate", label: "人工确认" },
] as const;

const DECISION_OPTIONS = [
  { value: "approved", label: "可以放行" },
  { value: "changes_requested", label: "还要再改" },
  { value: "blocked", label: "先别往后推" },
] as const;

function normalizeSelection(textarea: HTMLTextAreaElement | null): SelectionSnapshot {
  if (!textarea) {
    return { start: null, end: null, text: "" };
  }
  const start = textarea.selectionStart ?? 0;
  const end = textarea.selectionEnd ?? 0;
  if (end <= start) {
    return { start: null, end: null, text: "" };
  }
  return {
    start,
    end,
    text: textarea.value.slice(start, end),
  };
}

function normalizeFocusPoints(value: string): string[] {
  return value
    .split(/[\n/、；;]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatCommentStatus(status: string): string {
  const labels: Record<string, string> = {
    open: "继续盯",
    in_progress: "处理中",
    resolved: "已解决",
  };
  return labels[status] ?? status;
}

function commentTone(status: string): string {
  if (status === "resolved") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (status === "in_progress") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  return "border-amber-200 bg-amber-50 text-amber-700";
}

function truncateText(value: string | null | undefined, limit = 110): string {
  const text = (value ?? "").trim().replace(/\s+/g, " ");
  if (!text) {
    return "";
  }
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, limit)}...`;
}

export function ChapterReviewPanel({
  activeChapter,
  draftText,
  draftDirty,
  reviewWorkspace,
  chapterVersions,
  loading,
  submittingActionKey,
  editorTextareaRef,
  onCreateComment,
  onUpdateComment,
  onDeleteComment,
  onCreateCheckpoint,
  onUpdateCheckpoint,
  onCreateDecision,
  onRollback,
  onRewriteSelection,
}: ChapterReviewPanelProps) {
  const [selection, setSelection] = useState<SelectionSnapshot>({
    start: null,
    end: null,
    text: "",
  });
  const [commentBody, setCommentBody] = useState("");
  const [commentAssigneeId, setCommentAssigneeId] = useState("");
  const [replyParentId, setReplyParentId] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [checkpointType, setCheckpointType] = useState("story_turn");
  const [checkpointTitle, setCheckpointTitle] = useState("");
  const [checkpointDescription, setCheckpointDescription] = useState("");
  const [decisionVerdict, setDecisionVerdict] = useState("changes_requested");
  const [decisionSummary, setDecisionSummary] = useState("");
  const [decisionFocusPoints, setDecisionFocusPoints] = useState("");
  const [rewriteInstruction, setRewriteInstruction] = useState(
    "把这段写得更顺一点，情绪和动作的衔接更稳。",
  );

  const reviewThreads = useMemo(
    () => buildReviewCommentThreads(reviewWorkspace?.comments ?? []),
    [reviewWorkspace?.comments],
  );
  const versionList = useMemo(
    () => [...chapterVersions].sort((left, right) => right.version_number - left.version_number),
    [chapterVersions],
  );
  const actionLockedReason = !activeChapter
    ? "先把这一章保存成正式章节，系统才能开始记版本、挂批注和做回退。"
    : draftDirty
      ? "当前正文还有未保存改动。先保存正文，再做批注、确认点、回退版本或改写选区，避免记录错位。"
      : null;
  const hasSelection =
    selection.start !== null &&
    selection.end !== null &&
    selection.end > selection.start &&
    selection.text.trim().length > 0;

  useEffect(() => {
    // 这里持续监听编辑器选区，保证右侧“重写这段 / 留个批注”能准确拿到正文中的定位。
    const textarea = editorTextareaRef.current;
    const syncSelection = () => {
      setSelection(normalizeSelection(editorTextareaRef.current));
    };

    syncSelection();
    if (!textarea) {
      return;
    }

    textarea.addEventListener("select", syncSelection);
    textarea.addEventListener("keyup", syncSelection);
    textarea.addEventListener("mouseup", syncSelection);

    return () => {
      textarea.removeEventListener("select", syncSelection);
      textarea.removeEventListener("keyup", syncSelection);
      textarea.removeEventListener("mouseup", syncSelection);
    };
  }, [draftText, editorTextareaRef]);

  useEffect(() => {
    // 章节切换时重置局部表单，避免把上一章的批注/结论误带到下一章。
    setCommentBody("");
    setCommentAssigneeId("");
    setReplyParentId(null);
    setReplyBody("");
    setCheckpointType("story_turn");
    setCheckpointTitle("");
    setCheckpointDescription("");
    setDecisionVerdict("changes_requested");
    setDecisionSummary("");
    setDecisionFocusPoints("");
    setSelection(normalizeSelection(editorTextareaRef.current));
  }, [activeChapter?.id, editorTextareaRef]);

  function isSubmitting(key: string): boolean {
    return submittingActionKey === key;
  }

  async function handleCreateRootComment() {
    if (!commentBody.trim()) {
      return;
    }
    const success = await onCreateComment({
      body: commentBody.trim(),
      assignee_user_id: commentAssigneeId || null,
      selection_start: hasSelection ? selection.start : null,
      selection_end: hasSelection ? selection.end : null,
      selection_text: hasSelection ? selection.text : null,
    });
    if (success) {
      setCommentBody("");
      setCommentAssigneeId("");
    }
  }

  async function handleCreateReply(parentCommentId: string) {
    if (!replyBody.trim()) {
      return;
    }
    const success = await onCreateComment({
      body: replyBody.trim(),
      parent_comment_id: parentCommentId,
    });
    if (success) {
      setReplyParentId(null);
      setReplyBody("");
    }
  }

  async function handleRewriteSelection() {
    if (!hasSelection || !rewriteInstruction.trim()) {
      return;
    }
    const response = await onRewriteSelection({
      selection_start: selection.start as number,
      selection_end: selection.end as number,
      instruction: rewriteInstruction.trim(),
    });
    if (!response) {
      return;
    }

    const textarea = editorTextareaRef.current;
    if (!textarea) {
      return;
    }

    // 改写完成后重新高亮新片段，方便写手立刻看到被替换的位置。
    window.requestAnimationFrame(() => {
      textarea.focus();
      textarea.setSelectionRange(
        response.selection_start,
        response.rewritten_selection_end,
      );
      setSelection({
        start: response.selection_start,
        end: response.rewritten_selection_end,
        text: response.rewritten_text,
      });
    });
  }

  async function handleCreateCheckpoint() {
    if (!checkpointTitle.trim()) {
      return;
    }
    const success = await onCreateCheckpoint({
      checkpoint_type: checkpointType,
      title: checkpointTitle.trim(),
      description: checkpointDescription.trim() || null,
    });
    if (success) {
      setCheckpointType("story_turn");
      setCheckpointTitle("");
      setCheckpointDescription("");
    }
  }

  async function handleCreateDecision() {
    if (!decisionSummary.trim()) {
      return;
    }
    const success = await onCreateDecision({
      verdict: decisionVerdict,
      summary: decisionSummary.trim(),
      focus_points: normalizeFocusPoints(decisionFocusPoints),
    });
    if (success) {
      setDecisionSummary("");
      setDecisionFocusPoints("");
    }
  }

  if (!activeChapter) {
    return (
      <section className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
        <p className="text-xs uppercase tracking-[0.24em] text-copper">章节收口台</p>
        <h2 className="mt-2 text-2xl font-semibold">先存正文，再开始记版本和收口</h2>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-black/62">
          这一块只处理正式章节。你先在上面点一次“保存正文”，下面就会自动出现版本记录、批注、确认点和本章结论。
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-[36px] border border-black/10 bg-white/82 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.24em] text-copper">章节收口台</p>
          <h2 className="mt-2 text-2xl font-semibold">版本、批注、确认点，都在这一处收口</h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-black/62">
            这里不让你看后台流程，只把真正会影响这章能不能继续往下推的东西摆出来。
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-black/55">
            当前版本 V{activeChapter.current_version_number}
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-black/55">
            开放批注 {reviewWorkspace?.open_comment_count ?? 0}
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-black/55">
            待确认 {reviewWorkspace?.pending_checkpoint_count ?? 0}
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-black/55">
            已记版本 {chapterVersions.length}
          </span>
        </div>
      </div>

      {actionLockedReason ? (
        <div className="mt-5 rounded-[24px] border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-7 text-amber-800">
          {actionLockedReason}
        </div>
      ) : null}

      {loading ? (
        <div className="mt-6 rounded-[28px] border border-black/10 bg-[#fbfaf5] p-5 text-sm text-black/55">
          正在同步这章的版本、批注和确认记录...
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="space-y-6">
          <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">版本台</p>
                <p className="mt-2 text-sm leading-7 text-black/60">
                  每次正式保存和回退都会留痕。退回旧版本时，系统会把它重新记成一版新的当前稿。
                </p>
              </div>
              <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
                共 {versionList.length} 版
              </span>
            </div>

            <div className="mt-4 max-h-[420px] space-y-3 overflow-y-auto pr-1">
              {versionList.length > 0 ? (
                versionList.map((version) => {
                  const isCurrent =
                    version.version_number === activeChapter.current_version_number;
                  return (
                    <article
                      key={version.id}
                      className="rounded-[24px] border border-black/10 bg-white p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold">V{version.version_number}</p>
                            {isCurrent ? (
                              <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-[11px] text-emerald-700">
                                当前稿
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-2 text-sm leading-7 text-black/65">
                            {version.change_reason?.trim() || "这版没有额外备注。"}
                          </p>
                          <p className="mt-2 text-xs text-black/45">
                            约 {version.content.length} 字符
                          </p>
                        </div>
                        <button
                          className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={
                            Boolean(actionLockedReason) ||
                            isCurrent ||
                            isSubmitting(`rollback:${version.id}`)
                          }
                          onClick={() => void onRollback(version.id, version.version_number)}
                          type="button"
                        >
                          {isSubmitting(`rollback:${version.id}`) ? "退回中..." : "退回这版"}
                        </button>
                      </div>
                    </article>
                  );
                })
              ) : (
                <div className="rounded-[24px] border border-dashed border-black/12 bg-white p-4 text-sm text-black/50">
                  这一章目前还只有初始版本，后续保存后会继续累积。
                </div>
              )}
            </div>
          </section>

          <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
            <p className="text-sm font-semibold">重写这段</p>
            <p className="mt-2 text-sm leading-7 text-black/60">
              先在左侧正文里选中一段，再告诉系统你想把这段修成什么感觉。
            </p>

            <div className="mt-4 rounded-[24px] border border-black/10 bg-white p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm font-medium">
                  {hasSelection
                    ? `已选中 ${selection.text.trim().length} 个字符`
                    : "还没有选中正文片段"}
                </p>
                <button
                  className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                  onClick={() =>
                    setSelection(normalizeSelection(editorTextareaRef.current))
                  }
                  type="button"
                >
                  刷新选区
                </button>
              </div>
              <p className="mt-3 text-sm leading-7 text-black/62">
                {hasSelection
                  ? `当前片段：${truncateText(selection.text, 140)}`
                  : "你在正文中框选的内容会显示在这里。"}
              </p>
            </div>

            <label className="mt-4 block">
              <span className="text-sm text-black/60">你想怎么改这段</span>
              <textarea
                className="mt-2 min-h-[120px] w-full rounded-[24px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
                placeholder="比如：把这段写得更狠一点，但不要改掉既有设定。"
                value={rewriteInstruction}
                onChange={(event) => setRewriteInstruction(event.target.value)}
              />
            </label>

            <button
              className="mt-4 rounded-full bg-[#566246] px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={
                Boolean(actionLockedReason) ||
                !hasSelection ||
                !rewriteInstruction.trim() ||
                isSubmitting("rewrite-selection")
              }
              onClick={() => void handleRewriteSelection()}
              type="button"
            >
              {isSubmitting("rewrite-selection") ? "改写中..." : "重写这段"}
            </button>
          </section>
        </div>

        <div className="space-y-6">
          <section className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">批注区</p>
                <p className="mt-2 text-sm leading-7 text-black/60">
                  有问题就留一句，能定位到具体句段最好，后面处理时不容易跑偏。
                </p>
              </div>
              <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
                已解决 {reviewWorkspace?.resolved_comment_count ?? 0}
              </span>
            </div>

            <div className="mt-4 rounded-[24px] border border-black/10 bg-white p-4">
              <div className="rounded-[20px] border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs leading-6 text-black/52">
                {hasSelection
                  ? `会把批注挂在这段上：${truncateText(selection.text, 120)}`
                  : "没有选中正文时，会把这条记成整章批注。"}
              </div>

              <textarea
                className="mt-3 min-h-[120px] w-full rounded-[22px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
                placeholder="这里写你想提醒自己的点，比如：主角这句口气太像反派了。"
                value={commentBody}
                onChange={(event) => setCommentBody(event.target.value)}
              />

              {reviewWorkspace?.assignable_members.length ? (
                <label className="mt-3 block">
                  <span className="text-xs text-black/55">这条先交给谁盯</span>
                  <select
                    className="mt-2 w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-3 py-2 text-sm outline-none"
                    value={commentAssigneeId}
                    onChange={(event) => setCommentAssigneeId(event.target.value)}
                  >
                    <option value="">先不指定</option>
                    {reviewWorkspace.assignable_members.map((member) => (
                      <option key={member.user_id} value={member.user_id}>
                        {member.email}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}

              <button
                className="mt-4 rounded-full bg-copper px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={
                  Boolean(actionLockedReason) ||
                  !reviewWorkspace?.can_comment ||
                  !commentBody.trim() ||
                  isSubmitting("comment:create")
                }
                onClick={() => void handleCreateRootComment()}
                type="button"
              >
                {isSubmitting("comment:create") ? "记录中..." : "留个批注"}
              </button>
            </div>

            <div className="mt-4 space-y-3">
              {reviewThreads.length > 0 ? (
                reviewThreads.map((thread) => (
                  <article
                    key={thread.root.id}
                    className="rounded-[24px] border border-black/10 bg-white p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-sm font-semibold">{thread.root.author_email}</p>
                          <span
                            className={`rounded-full border px-2.5 py-1 text-[11px] ${commentTone(thread.root.status)}`}
                          >
                            {formatCommentStatus(thread.root.status)}
                          </span>
                          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-2.5 py-1 text-[11px] text-black/50">
                            V{thread.root.chapter_version_number}
                          </span>
                        </div>
                        <p className="mt-2 text-xs text-black/45">
                          {formatDateTime(thread.root.created_at)}
                        </p>
                      </div>
                      {thread.root.reply_count > 0 ? (
                        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-2.5 py-1 text-[11px] text-black/50">
                          回复 {thread.root.reply_count}
                        </span>
                      ) : null}
                    </div>

                    {thread.root.selection_text ? (
                      <div className="mt-3 rounded-[20px] border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs leading-6 text-black/55">
                        关联片段：{truncateText(thread.root.selection_text, 120)}
                      </div>
                    ) : null}

                    <p className="mt-3 text-sm leading-7 text-black/72">{thread.root.body}</p>

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      {thread.root.can_change_status
                        ? COMMENT_STATUS_OPTIONS.map((option) => (
                            <button
                              key={option.value}
                              className={`rounded-full border px-3 py-2 text-xs font-semibold transition ${
                                thread.root.status === option.value
                                  ? "border-black/15 bg-[#f4ede2] text-black/80"
                                  : "border-black/10 bg-[#fbfaf5] text-black/62 hover:bg-[#f6f0e6]"
                              }`}
                              disabled={
                                Boolean(actionLockedReason) ||
                                isSubmitting(
                                  `comment:status:${thread.root.id}:${option.value}`,
                                )
                              }
                              onClick={() =>
                                void onUpdateComment(thread.root.id, {
                                  status: option.value,
                                })
                              }
                              type="button"
                            >
                              {thread.root.status === option.value
                                ? `当前${option.label}`
                                : option.label}
                            </button>
                          ))
                        : null}

                      {thread.root.can_assign &&
                      reviewWorkspace?.assignable_members.length ? (
                        <select
                          className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs text-black/65 outline-none"
                          value={thread.root.assignee_user_id ?? ""}
                          disabled={
                            Boolean(actionLockedReason) ||
                            isSubmitting(`comment:assign:${thread.root.id}`)
                          }
                          onChange={(event) =>
                            void onUpdateComment(thread.root.id, {
                              assignee_user_id: event.target.value || null,
                            })
                          }
                        >
                          <option value="">先不指定负责人</option>
                          {reviewWorkspace.assignable_members.map((member) => (
                            <option key={member.user_id} value={member.user_id}>
                              交给 {member.email}
                            </option>
                          ))}
                        </select>
                      ) : null}

                      <button
                        className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/65 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-50"
                        disabled={Boolean(actionLockedReason)}
                        onClick={() =>
                          setReplyParentId((current) =>
                            current === thread.root.id ? null : thread.root.id,
                          )
                        }
                        type="button"
                      >
                        {replyParentId === thread.root.id ? "收起回复" : "回复"}
                      </button>

                      {thread.root.can_delete ? (
                        <button
                          className="rounded-full border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                          disabled={
                            Boolean(actionLockedReason) ||
                            isSubmitting(`comment:delete:${thread.root.id}`)
                          }
                          onClick={() => void onDeleteComment(thread.root.id)}
                          type="button"
                        >
                          删除
                        </button>
                      ) : null}
                    </div>

                    {thread.root.assignee_email ? (
                      <p className="mt-3 text-xs text-black/45">
                        当前负责人：{thread.root.assignee_email}
                      </p>
                    ) : null}

                    {replyParentId === thread.root.id ? (
                      <div className="mt-4 rounded-[20px] border border-black/10 bg-[#fbfaf5] p-3">
                        <textarea
                          className="min-h-[96px] w-full rounded-[18px] border border-black/10 bg-white px-3 py-3 text-sm leading-7 outline-none"
                          placeholder="补一句追问、解释或处理结果。"
                          value={replyBody}
                          onChange={(event) => setReplyBody(event.target.value)}
                        />
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            className="rounded-full bg-copper px-4 py-2 text-xs font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={
                              Boolean(actionLockedReason) ||
                              !replyBody.trim() ||
                              isSubmitting(`comment:reply:${thread.root.id}`)
                            }
                            onClick={() => void handleCreateReply(thread.root.id)}
                            type="button"
                          >
                            {isSubmitting(`comment:reply:${thread.root.id}`)
                              ? "回复中..."
                              : "发出回复"}
                          </button>
                          <button
                            className="rounded-full border border-black/10 bg-white px-4 py-2 text-xs font-semibold text-black/62 transition hover:bg-[#f6f0e6]"
                            onClick={() => {
                              setReplyParentId(null);
                              setReplyBody("");
                            }}
                            type="button"
                          >
                            取消
                          </button>
                        </div>
                      </div>
                    ) : null}

                    {thread.replies.length > 0 ? (
                      <div className="mt-4 space-y-3 border-t border-dashed border-black/10 pt-4">
                        {thread.replies.map((reply) => (
                          <div
                            key={reply.id}
                            className="rounded-[20px] border border-black/10 bg-[#fbfaf5] p-3"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-xs font-semibold text-black/72">
                                {reply.author_email}
                              </p>
                              <span
                                className={`rounded-full border px-2 py-0.5 text-[10px] ${commentTone(reply.status)}`}
                              >
                                {formatCommentStatus(reply.status)}
                              </span>
                              <span className="text-[11px] text-black/42">
                                {formatDateTime(reply.created_at)}
                              </span>
                            </div>
                            <p className="mt-2 text-sm leading-7 text-black/68">{reply.body}</p>
                            <div className="mt-3 flex flex-wrap gap-2">
                              {reply.can_change_status
                                ? COMMENT_STATUS_OPTIONS.map((option) => (
                                    <button
                                      key={`${reply.id}-${option.value}`}
                                      className={`rounded-full border px-2.5 py-1.5 text-[11px] font-semibold transition ${
                                        reply.status === option.value
                                          ? "border-black/15 bg-white text-black/78"
                                          : "border-black/10 bg-white text-black/58 hover:bg-[#f6f0e6]"
                                      }`}
                                      disabled={
                                        Boolean(actionLockedReason) ||
                                        isSubmitting(
                                          `comment:status:${reply.id}:${option.value}`,
                                        )
                                      }
                                      onClick={() =>
                                        void onUpdateComment(reply.id, {
                                          status: option.value,
                                        })
                                      }
                                      type="button"
                                    >
                                      {option.label}
                                    </button>
                                  ))
                                : null}
                              {reply.can_delete ? (
                                <button
                                  className="rounded-full border border-red-200 bg-red-50 px-2.5 py-1.5 text-[11px] font-semibold text-red-700 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                                  disabled={
                                    Boolean(actionLockedReason) ||
                                    isSubmitting(`comment:delete:${reply.id}`)
                                  }
                                  onClick={() => void onDeleteComment(reply.id)}
                                  type="button"
                                >
                                  删除回复
                                </button>
                              ) : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </article>
                ))
              ) : (
                <div className="rounded-[24px] border border-dashed border-black/12 bg-white p-4 text-sm text-black/50">
                  这章还没有批注。写到觉得哪句不稳、哪段有风险时，直接在这里留。
                </div>
              )}
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
              <p className="text-sm font-semibold">挂个确认点</p>
              <p className="mt-2 text-sm leading-7 text-black/60">
                用来卡住关键转折、大纲关口或分支选择，避免后面写着写着走偏。
              </p>

              <label className="mt-4 block">
                <span className="text-xs text-black/55">确认点类型</span>
                <select
                  className="mt-2 w-full rounded-[18px] border border-black/10 bg-white px-3 py-2 text-sm outline-none"
                  value={checkpointType}
                  onChange={(event) => setCheckpointType(event.target.value)}
                >
                  {CHECKPOINT_TYPE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="mt-3 block">
                <span className="text-xs text-black/55">标题</span>
                <input
                  className="mt-2 w-full rounded-[18px] border border-black/10 bg-white px-3 py-2 text-sm outline-none"
                  placeholder="比如：主角这里能不能直接暴露底牌？"
                  value={checkpointTitle}
                  onChange={(event) => setCheckpointTitle(event.target.value)}
                />
              </label>

              <label className="mt-3 block">
                <span className="text-xs text-black/55">补充说明</span>
                <textarea
                  className="mt-2 min-h-[96px] w-full rounded-[18px] border border-black/10 bg-white px-3 py-3 text-sm leading-7 outline-none"
                  placeholder="把卡点背景写清楚，后续处理会快很多。"
                  value={checkpointDescription}
                  onChange={(event) => setCheckpointDescription(event.target.value)}
                />
              </label>

              <button
                className="mt-4 rounded-full bg-[#2f5d62] px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={
                  Boolean(actionLockedReason) ||
                  !reviewWorkspace?.can_request_checkpoint ||
                  !checkpointTitle.trim() ||
                  isSubmitting("checkpoint:create")
                }
                onClick={() => void handleCreateCheckpoint()}
                type="button"
              >
                {isSubmitting("checkpoint:create") ? "挂起中..." : "挂个确认点"}
              </button>

              <div className="mt-4 space-y-3">
                {reviewWorkspace?.checkpoints.length ? (
                  reviewWorkspace.checkpoints.map((checkpoint) => (
                    <article
                      key={checkpoint.id}
                      className="rounded-[22px] border border-black/10 bg-white p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold">{checkpoint.title}</p>
                            <span
                              className={`rounded-full border px-2.5 py-1 text-[11px] ${checkpointStatusTone(checkpoint.status)}`}
                            >
                              {formatCheckpointStatus(checkpoint.status)}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-black/45">
                            {formatCheckpointType(checkpoint.checkpoint_type)} · V
                            {checkpoint.chapter_version_number}
                          </p>
                        </div>
                      </div>
                      {checkpoint.description ? (
                        <p className="mt-3 text-sm leading-7 text-black/68">
                          {checkpoint.description}
                        </p>
                      ) : null}
                      {checkpoint.decision_note ? (
                        <div className="mt-3 rounded-[18px] border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs leading-6 text-black/55">
                          处理说明：{checkpoint.decision_note}
                        </div>
                      ) : null}
                      <p className="mt-3 text-xs text-black/42">
                        发起人：{checkpoint.requester_email}
                        {checkpoint.decided_by_email
                          ? ` · 处理人：${checkpoint.decided_by_email}`
                          : ""}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {checkpoint.can_decide ? (
                          <>
                            <button
                              className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                              disabled={
                                Boolean(actionLockedReason) ||
                                isSubmitting(`checkpoint:approve:${checkpoint.id}`)
                              }
                              onClick={() =>
                                void onUpdateCheckpoint(checkpoint.id, {
                                  status: "approved",
                                })
                              }
                              type="button"
                            >
                              通过
                            </button>
                            <button
                              className="rounded-full border border-red-200 bg-red-50 px-3 py-2 text-xs font-semibold text-red-700 transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                              disabled={
                                Boolean(actionLockedReason) ||
                                isSubmitting(`checkpoint:reject:${checkpoint.id}`)
                              }
                              onClick={() =>
                                void onUpdateCheckpoint(checkpoint.id, {
                                  status: "rejected",
                                })
                              }
                              type="button"
                            >
                              驳回
                            </button>
                          </>
                        ) : null}
                        {checkpoint.can_cancel ? (
                          <button
                            className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-semibold text-black/65 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-50"
                            disabled={
                              Boolean(actionLockedReason) ||
                              isSubmitting(`checkpoint:cancel:${checkpoint.id}`)
                            }
                            onClick={() =>
                              void onUpdateCheckpoint(checkpoint.id, {
                                status: "cancelled",
                              })
                            }
                            type="button"
                          >
                            取消
                          </button>
                        ) : null}
                      </div>
                    </article>
                  ))
                ) : (
                  <div className="rounded-[22px] border border-dashed border-black/12 bg-white p-4 text-sm text-black/50">
                    当前没有挂起中的确认点。
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-[30px] border border-black/10 bg-[#fbfaf5] p-5">
              <p className="text-sm font-semibold">给这一章下结论</p>
              <p className="mt-2 text-sm leading-7 text-black/60">
                当你觉得这章已经差不多了，就在这里留一句结论，告诉后面这章能不能继续往下推。
              </p>

              <label className="mt-4 block">
                <span className="text-xs text-black/55">结论</span>
                <select
                  className="mt-2 w-full rounded-[18px] border border-black/10 bg-white px-3 py-2 text-sm outline-none"
                  value={decisionVerdict}
                  onChange={(event) => setDecisionVerdict(event.target.value)}
                >
                  {DECISION_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="mt-3 block">
                <span className="text-xs text-black/55">结论说明</span>
                <textarea
                  className="mt-2 min-h-[112px] w-full rounded-[18px] border border-black/10 bg-white px-3 py-3 text-sm leading-7 outline-none"
                  placeholder="比如：情绪线已经立住，但高潮段还差一点爆点。"
                  value={decisionSummary}
                  onChange={(event) => setDecisionSummary(event.target.value)}
                />
              </label>

              <label className="mt-3 block">
                <span className="text-xs text-black/55">聚焦点</span>
                <input
                  className="mt-2 w-full rounded-[18px] border border-black/10 bg-white px-3 py-2 text-sm outline-none"
                  placeholder="用 / 隔开，例如：高潮不够狠 / 女主反应偏弱"
                  value={decisionFocusPoints}
                  onChange={(event) => setDecisionFocusPoints(event.target.value)}
                />
              </label>

              <button
                className="mt-4 rounded-full bg-[#566246] px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                disabled={
                  Boolean(actionLockedReason) ||
                  !reviewWorkspace?.can_decide ||
                  !decisionSummary.trim() ||
                  isSubmitting("decision:create")
                }
                onClick={() => void handleCreateDecision()}
                type="button"
              >
                {isSubmitting("decision:create") ? "提交中..." : "记下这条结论"}
              </button>

              <div className="mt-4 space-y-3">
                {reviewWorkspace?.decisions.length ? (
                  reviewWorkspace.decisions.map((decision) => (
                    <article
                      key={decision.id}
                      className="rounded-[22px] border border-black/10 bg-white p-4"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold">
                              {decision.reviewer_email}
                            </p>
                            <span
                              className={`rounded-full border px-2.5 py-1 text-[11px] ${reviewVerdictTone(decision.verdict)}`}
                            >
                              {formatReviewVerdict(decision.verdict)}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-black/45">
                            {formatDateTime(decision.created_at)} · V
                            {decision.chapter_version_number}
                          </p>
                        </div>
                      </div>
                      <p className="mt-3 text-sm leading-7 text-black/68">
                        {decision.summary}
                      </p>
                      {decision.focus_points.length ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {decision.focus_points.map((point) => (
                            <span
                              key={`${decision.id}-${point}`}
                              className="rounded-full border border-black/10 bg-[#fbfaf5] px-2.5 py-1 text-[11px] text-black/55"
                            >
                              {point}
                            </span>
                          ))}
                        </div>
                      ) : null}
                    </article>
                  ))
                ) : (
                  <div className="rounded-[22px] border border-dashed border-black/12 bg-white p-4 text-sm text-black/50">
                    这章还没有正式结论。等你觉得差不多了，再在这里留一句。
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>
      </div>
    </section>
  );
}
