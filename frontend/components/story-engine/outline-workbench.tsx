"use client";

import { useMemo, useState } from "react";

import { StoryDeliberationPanel } from "@/components/story-engine/story-deliberation-panel";
import type { OutlineStressTestResponse, StoryEngineIssue, StoryOutline } from "@/types/api";

type OutlineWorkbenchProps = {
  outlines: StoryOutline[];
  result: OutlineStressTestResponse | null;
  idea: string;
  genre: string;
  tone: string;
  sourceMaterial: string;
  sourceMaterialName: string | null;
  targetChapterWords: number;
  targetTotalWords: number;
  estimatedChapterCount: number;
  loading: boolean;
  savingGoalProfile: boolean;
  updatingOutlineId: string | null;
  onIdeaChange: (value: string) => void;
  onGenreChange: (value: string) => void;
  onToneChange: (value: string) => void;
  onSourceMaterialChange: (value: string, name?: string | null) => void;
  onClearSourceMaterial: () => void;
  onTargetChapterWordsChange: (value: number) => void;
  onTargetTotalWordsChange: (value: number) => void;
  onSaveGoalProfile: () => void;
  onRunStressTest: () => void;
  onUpdateOutline: (outlineId: string, payload: { title: string; content: string }) => void;
  onOpenDraftStep: () => void;
};

const LEVEL_LABELS: Record<string, string> = {
  level_1: "一级主线",
  level_2: "二级分卷",
  level_3: "三级章节",
};

const ISSUE_TONES: Record<string, string> = {
  critical: "border-red-200 bg-red-50 text-red-700",
  high: "border-orange-200 bg-orange-50 text-orange-700",
  medium: "border-amber-200 bg-amber-50 text-amber-700",
  low: "border-sky-200 bg-sky-50 text-sky-700",
};

function IssueCard({ issue }: { issue: StoryEngineIssue }) {
  return (
    <article className={`rounded-[24px] border p-4 ${ISSUE_TONES[issue.severity] ?? ISSUE_TONES.low}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">{issue.title}</p>
        <span className="text-xs uppercase tracking-[0.14em]">{issue.severity}</span>
      </div>
      <p className="mt-2 text-sm leading-7">{issue.detail}</p>
      {issue.suggestion ? <p className="mt-3 text-sm">建议：{issue.suggestion}</p> : null}
    </article>
  );
}

function OutlineColumn({
  title,
  items,
  editingOutlineId,
  editingTitle,
  editingContent,
  savingOutlineId,
  onEditingTitleChange,
  onEditingContentChange,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
}: {
  title: string;
  items: StoryOutline[];
  editingOutlineId: string | null;
  editingTitle: string;
  editingContent: string;
  savingOutlineId: string | null;
  onEditingTitleChange: (value: string) => void;
  onEditingContentChange: (value: string) => void;
  onStartEdit: (item: StoryOutline) => void;
  onCancelEdit: () => void;
  onSaveEdit: (item: StoryOutline) => void;
}) {
  return (
    <section className="rounded-[28px] border border-black/10 bg-white/85 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
          {items.length} 条
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {items.length === 0 ? (
          <div className="rounded-[24px] border border-dashed border-black/10 bg-[#fbfaf5] p-5 text-sm text-black/45">
            这一层还没有内容。
          </div>
        ) : null}

        {items.map((item) => {
          const isEditing = editingOutlineId === item.outline_id;
          return (
            <article
              key={item.outline_id}
              className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-4"
            >
              {isEditing ? (
                <div className="space-y-3">
                  <input
                    className="w-full rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm outline-none"
                    value={editingTitle}
                    onChange={(event) => onEditingTitleChange(event.target.value)}
                  />
                  <textarea
                    className="min-h-[140px] w-full rounded-[18px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
                    value={editingContent}
                    onChange={(event) => onEditingContentChange(event.target.value)}
                  />
                  <div className="flex flex-wrap gap-2">
                    <button
                      className="rounded-full bg-copper px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={savingOutlineId === item.outline_id}
                      onClick={() => onSaveEdit(item)}
                      type="button"
                    >
                      {savingOutlineId === item.outline_id ? "保存中..." : "保存修改"}
                    </button>
                    <button
                      className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-black/70"
                      onClick={onCancelEdit}
                      type="button"
                    >
                      取消
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold">{item.title}</p>
                      <p className="mt-2 text-sm leading-7 text-black/65">{item.content}</p>
                    </div>
                    {item.locked ? (
                      <span className="rounded-full border border-copper/25 bg-copper/10 px-3 py-1 text-xs text-copper">
                        锁定
                      </span>
                    ) : null}
                  </div>
                  {!item.locked ? (
                    <div className="mt-4">
                      <button
                        className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-black/70"
                        onClick={() => onStartEdit(item)}
                        type="button"
                      >
                        编辑
                      </button>
                    </div>
                  ) : (
                    <p className="mt-4 text-xs text-black/45">一级主线锁定后不可直接修改。</p>
                  )}
                </>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function OutlineWorkbench({
  outlines,
  result,
  idea,
  genre,
  tone,
  sourceMaterial,
  sourceMaterialName,
  targetChapterWords,
  targetTotalWords,
  estimatedChapterCount,
  loading,
  savingGoalProfile,
  updatingOutlineId,
  onIdeaChange,
  onGenreChange,
  onToneChange,
  onSourceMaterialChange,
  onClearSourceMaterial,
  onTargetChapterWordsChange,
  onTargetTotalWordsChange,
  onSaveGoalProfile,
  onRunStressTest,
  onUpdateOutline,
  onOpenDraftStep,
}: OutlineWorkbenchProps) {
  const [editingOutlineId, setEditingOutlineId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [editingContent, setEditingContent] = useState("");

  const displayOutlines = useMemo(
    () =>
      result
        ? [
            ...result.locked_level_1_outlines,
            ...result.editable_level_2_outlines,
            ...result.editable_level_3_outlines,
          ]
        : outlines,
    [outlines, result],
  );

  const grouped = useMemo(
    () => ({
      level_1: displayOutlines.filter((item) => item.level === "level_1"),
      level_2: displayOutlines.filter((item) => item.level === "level_2"),
      level_3: displayOutlines.filter((item) => item.level === "level_3"),
    }),
    [displayOutlines],
  );

  const hasOutlineResult = displayOutlines.length > 0;
  const canGenerate = idea.trim().length > 0 || sourceMaterial.trim().length > 0;

  async function handleUploadFile(file: File | null) {
    if (!file) {
      return;
    }
    const text = await file.text();
    onSourceMaterialChange(text, file.name);
  }

  function handleStartEdit(item: StoryOutline) {
    setEditingOutlineId(item.outline_id);
    setEditingTitle(item.title);
    setEditingContent(item.content);
  }

  function handleCancelEdit() {
    setEditingOutlineId(null);
    setEditingTitle("");
    setEditingContent("");
  }

  function handleSaveEdit(item: StoryOutline) {
    if (!editingTitle.trim() || !editingContent.trim()) {
      return;
    }
    void onUpdateOutline(item.outline_id, {
      title: editingTitle.trim(),
      content: editingContent.trim(),
    });
    handleCancelEdit();
  }

  return (
    <section className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-[1.08fr_0.92fr]">
        <section className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_20px_50px_rgba(16,20,23,0.05)]">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-copper">第一步</p>
              <h2 className="mt-2 text-2xl font-semibold">输入想法，或者上传已有大纲</h2>
            </div>
            {hasOutlineResult ? (
              <button
                className="rounded-full bg-[#566246] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90"
                onClick={onOpenDraftStep}
                type="button"
              >
                去写第一章
              </button>
            ) : null}
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="text-sm text-black/60">小说类别</span>
              <input
                className="mt-2 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                value={genre}
                onChange={(event) => onGenreChange(event.target.value)}
                placeholder="玄幻 / 科幻 / 古言 / 都市"
              />
            </label>
            <label className="block">
              <span className="text-sm text-black/60">气质</span>
              <input
                className="mt-2 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                value={tone}
                onChange={(event) => onToneChange(event.target.value)}
                placeholder="热血 / 冷峻 / 轻快 / 诡谲"
              />
            </label>
          </div>

          <label className="mt-5 block">
            <span className="text-sm text-black/60">一句想法</span>
            <textarea
              className="mt-2 min-h-[180px] w-full rounded-[24px] border border-black/10 bg-[#fbfaf5] px-5 py-4 text-sm leading-7 outline-none"
              placeholder="主角是谁、想得到什么、最大限制是什么、第一卷冲突是什么。"
              value={idea}
              onChange={(event) => onIdeaChange(event.target.value)}
            />
          </label>

          <section className="mt-5 rounded-[24px] border border-black/10 bg-[#fbfaf5] p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">上传已有大纲</p>
                <p className="mt-2 text-sm text-black/58">支持 `.txt` / `.md`，也可以直接把大纲原文贴到下面。</p>
              </div>
              <label className="inline-flex cursor-pointer rounded-full border border-black/10 bg-white px-4 py-3 text-sm font-semibold text-black/72">
                选择文件
                <input
                  className="hidden"
                  type="file"
                  accept=".txt,.md,text/plain,text/markdown"
                  onChange={(event) => void handleUploadFile(event.target.files?.[0] ?? null)}
                />
              </label>
            </div>

            <textarea
              className="mt-4 min-h-[180px] w-full rounded-[22px] border border-black/10 bg-white px-4 py-3 text-sm leading-7 outline-none"
              placeholder="如果你已经写好了粗大纲，直接贴进来。系统会先解读原文，再整理成三级大纲。"
              value={sourceMaterial}
              onChange={(event) => onSourceMaterialChange(event.target.value)}
            />

            <div className="mt-3 flex flex-wrap gap-2">
              {sourceMaterialName ? (
                <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
                  已载入：{sourceMaterialName}
                </span>
              ) : null}
              {sourceMaterial.trim().length > 0 ? (
                <button
                  className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/70"
                  onClick={onClearSourceMaterial}
                  type="button"
                >
                  清空大纲原文
                </button>
              ) : null}
            </div>
          </section>
        </section>

        <section className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_20px_50px_rgba(16,20,23,0.05)]">
          <p className="text-sm font-semibold">体量设定</p>

          <div className="mt-5 grid gap-4">
            <label className="block">
              <span className="text-sm text-black/60">目标总字数</span>
              <input
                className="mt-2 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                type="number"
                min={50000}
                step={10000}
                value={targetTotalWords}
                onChange={(event) => onTargetTotalWordsChange(Number(event.target.value || 1_000_000))}
              />
            </label>
            <label className="block">
              <span className="text-sm text-black/60">单章目标字数</span>
              <input
                className="mt-2 w-full rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                type="number"
                min={1000}
                step={500}
                value={targetChapterWords}
                onChange={(event) => onTargetChapterWordsChange(Number(event.target.value || 3000))}
              />
            </label>
          </div>

          <div className="mt-5 grid gap-3">
            <article className="rounded-[22px] border border-black/10 bg-[#fbfaf5] p-4">
              <p className="text-sm text-black/55">预计章节数</p>
              <p className="mt-2 text-2xl font-semibold">{estimatedChapterCount} 章</p>
            </article>
          </div>

          <div className="mt-5 grid gap-3">
            <button
              className="rounded-full bg-copper px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={loading || !canGenerate}
              onClick={onRunStressTest}
              type="button"
            >
              {loading ? "生成中..." : hasOutlineResult ? "重新生成三级大纲" : "生成三级大纲"}
            </button>
            <button
              className="rounded-full border border-black/10 bg-white px-5 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
              disabled={savingGoalProfile}
              onClick={onSaveGoalProfile}
              type="button"
            >
              {savingGoalProfile ? "保存中..." : "保存基础设定"}
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              生成后可继续修改二级、三级大纲
            </span>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              一级主线默认锁定
            </span>
          </div>
        </section>
      </div>

      {hasOutlineResult ? (
        <section className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_20px_50px_rgba(16,20,23,0.05)]">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.24em] text-copper">生成结果</p>
              <h2 className="mt-2 text-2xl font-semibold">三级大纲已经出来了</h2>
            </div>
            <button
              className="rounded-full bg-[#566246] px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90"
              onClick={onOpenDraftStep}
              type="button"
            >
              确认并开始第一章
            </button>
          </div>

          <div className="mt-5 flex flex-wrap gap-2">
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              一级 {grouped.level_1.length} 条
            </span>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              二级 {grouped.level_2.length} 条
            </span>
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              三级 {grouped.level_3.length} 条
            </span>
            {result ? (
              <span className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-1 text-xs text-copper">
                已查 {result.debate_rounds_completed} 轮
              </span>
            ) : null}
          </div>
        </section>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-3">
        <OutlineColumn
          title={LEVEL_LABELS.level_1}
          items={grouped.level_1}
          editingOutlineId={editingOutlineId}
          editingTitle={editingTitle}
          editingContent={editingContent}
          savingOutlineId={updatingOutlineId}
          onEditingTitleChange={setEditingTitle}
          onEditingContentChange={setEditingContent}
          onStartEdit={handleStartEdit}
          onCancelEdit={handleCancelEdit}
          onSaveEdit={handleSaveEdit}
        />
        <OutlineColumn
          title={LEVEL_LABELS.level_2}
          items={grouped.level_2}
          editingOutlineId={editingOutlineId}
          editingTitle={editingTitle}
          editingContent={editingContent}
          savingOutlineId={updatingOutlineId}
          onEditingTitleChange={setEditingTitle}
          onEditingContentChange={setEditingContent}
          onStartEdit={handleStartEdit}
          onCancelEdit={handleCancelEdit}
          onSaveEdit={handleSaveEdit}
        />
        <OutlineColumn
          title={LEVEL_LABELS.level_3}
          items={grouped.level_3}
          editingOutlineId={editingOutlineId}
          editingTitle={editingTitle}
          editingContent={editingContent}
          savingOutlineId={updatingOutlineId}
          onEditingTitleChange={setEditingTitle}
          onEditingContentChange={setEditingContent}
          onStartEdit={handleStartEdit}
          onCancelEdit={handleCancelEdit}
          onSaveEdit={handleSaveEdit}
        />
      </div>

      {result ? (
        <>
          <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <section className="rounded-[28px] border border-black/10 bg-white/85 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <h3 className="text-lg font-semibold">这轮需要注意的问题</h3>
              <div className="mt-4 space-y-3">
                {result.risk_report.length > 0 ? (
                  result.risk_report.map((issue) => (
                    <IssueCard
                      key={`${issue.source}-${issue.title}-${issue.detail}`}
                      issue={issue}
                    />
                  ))
                ) : (
                  <div className="rounded-[24px] border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                    当前骨架没有明显硬伤，可以直接进入第一章。
                  </div>
                )}
              </div>
            </section>

            <section className="rounded-[28px] border border-black/10 bg-white/85 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
              <h3 className="text-lg font-semibold">建议怎么补</h3>
              <div className="mt-4 space-y-3">
                {result.optimization_plan.length > 0 ? (
                  result.optimization_plan.map((item) => (
                    <div
                      key={item}
                      className="rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 text-black/65"
                    >
                      {item}
                    </div>
                  ))
                ) : (
                  <div className="rounded-[22px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm text-black/55">
                    当前没有额外补强项。
                  </div>
                )}
              </div>
            </section>
          </div>

          <StoryDeliberationPanel
            title="这次大纲怎么收口的"
            description="默认收起。需要时再展开看这一轮为什么这样定。"
            rounds={result.deliberation_rounds}
            emptyText="这次大纲结果还没有可展示的推演纪要。"
          />
        </>
      ) : null}
    </section>
  );
}
