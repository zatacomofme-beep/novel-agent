"use client";

import type { OutlineStressTestResponse, StoryEngineIssue, StoryOutline } from "@/types/api";

type OutlineWorkbenchProps = {
  outlines: StoryOutline[];
  result: OutlineStressTestResponse | null;
  idea: string;
  genre: string;
  tone: string;
  targetChapterCount: number;
  targetTotalWords: number;
  loading: boolean;
  onIdeaChange: (value: string) => void;
  onGenreChange: (value: string) => void;
  onToneChange: (value: string) => void;
  onTargetChapterCountChange: (value: number) => void;
  onTargetTotalWordsChange: (value: number) => void;
  onRunStressTest: () => void;
};

const LEVEL_LABELS: Record<string, string> = {
  level_1: "一级大纲",
  level_2: "二级大纲",
  level_3: "三级大纲",
};

const ISSUE_TONES: Record<string, string> = {
  critical: "border-red-200 bg-red-50 text-red-700",
  high: "border-orange-200 bg-orange-50 text-orange-700",
  medium: "border-amber-200 bg-amber-50 text-amber-700",
  low: "border-sky-200 bg-sky-50 text-sky-700",
};

function OutlineColumn({
  title,
  items,
}: {
  title: string;
  items: StoryOutline[];
}) {
  return (
    <section className="rounded-[28px] border border-black/10 bg-white/85 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
          {items.length} 节点
        </span>
      </div>
      <div className="mt-4 space-y-3">
        {items.length > 0 ? (
          items.map((item) => (
            <article
              key={item.outline_id}
              className="rounded-3xl border border-black/10 bg-[#fbfaf5] p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{item.title}</p>
                  <p className="mt-2 text-sm leading-7 text-black/65">{item.content}</p>
                </div>
                {item.locked ? (
                  <span className="rounded-full border border-copper/25 bg-copper/10 px-3 py-1 text-xs text-copper">
                    锁死
                  </span>
                ) : null}
              </div>
            </article>
          ))
        ) : (
          <div className="rounded-3xl border border-dashed border-black/10 bg-[#fbfaf5] p-5 text-sm leading-7 text-black/45">
            还没有生成这一层大纲。
          </div>
        )}
      </div>
    </section>
  );
}

function IssueCard({ issue }: { issue: StoryEngineIssue }) {
  return (
    <article className={`rounded-3xl border p-4 ${ISSUE_TONES[issue.severity] ?? ISSUE_TONES.low}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">{issue.title}</p>
        <span className="text-xs uppercase tracking-[0.14em]">{issue.severity}</span>
      </div>
      <p className="mt-2 text-sm leading-7">{issue.detail}</p>
      {issue.suggestion ? <p className="mt-3 text-sm">建议：{issue.suggestion}</p> : null}
    </article>
  );
}

export function OutlineWorkbench({
  outlines,
  result,
  idea,
  genre,
  tone,
  targetChapterCount,
  targetTotalWords,
  loading,
  onIdeaChange,
  onGenreChange,
  onToneChange,
  onTargetChapterCountChange,
  onTargetTotalWordsChange,
  onRunStressTest,
}: OutlineWorkbenchProps) {
  const displayOutlines = result
    ? [
        ...result.locked_level_1_outlines,
        ...result.editable_level_2_outlines,
        ...result.editable_level_3_outlines,
      ]
    : outlines;

  const grouped = {
    level_1: displayOutlines.filter((item) => item.level === "level_1"),
    level_2: displayOutlines.filter((item) => item.level === "level_2"),
    level_3: displayOutlines.filter((item) => item.level === "level_3"),
  };

  return (
    <section className="space-y-6">
      <div className="rounded-[36px] border border-black/10 bg-white/80 p-6 shadow-[0_24px_60px_rgba(16,20,23,0.06)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.24em] text-copper">大纲工作台</p>
            <h2 className="mt-2 text-2xl font-semibold">把脑洞压成可写的长线骨架</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-black/62">
              只输入你现在最模糊的故事想法，系统会把它压成锁死版主线、可编辑卷纲和可直接开写的章节细纲。
            </p>
          </div>
          <button
            className="rounded-full bg-copper px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={loading || idea.trim().length < 10}
            onClick={onRunStressTest}
            type="button"
          >
            {loading ? "测大纲漏洞中..." : "测大纲漏洞"}
          </button>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <label className="block">
            <span className="text-sm text-black/60">故事脑洞</span>
            <textarea
              className="mt-2 min-h-[140px] w-full rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 outline-none"
              placeholder="例如：主角前期极度怕水，却被迫在一座以海为神明的城市里生存..."
              value={idea}
              onChange={(event) => onIdeaChange(event.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm text-black/60">题材</span>
            <input
              className="mt-2 w-full rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
              value={genre}
              onChange={(event) => onGenreChange(event.target.value)}
              placeholder="玄幻 / 都市 / 科幻 / 古言..."
            />
          </label>
          <label className="block">
            <span className="text-sm text-black/60">气质</span>
            <input
              className="mt-2 w-full rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
              value={tone}
              onChange={(event) => onToneChange(event.target.value)}
              placeholder="冷峻、热血、诡谲、轻喜..."
            />
          </label>
          <div className="grid gap-4">
            <label className="block">
              <span className="text-sm text-black/60">目标章节数</span>
              <input
                className="mt-2 w-full rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                type="number"
                min={10}
                value={targetChapterCount}
                onChange={(event) => onTargetChapterCountChange(Number(event.target.value || 120))}
              />
            </label>
            <label className="block">
              <span className="text-sm text-black/60">目标总字数</span>
              <input
                className="mt-2 w-full rounded-[24px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none"
                type="number"
                min={50000}
                step={10000}
                value={targetTotalWords}
                onChange={(event) => onTargetTotalWordsChange(Number(event.target.value || 1000000))}
              />
            </label>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <OutlineColumn title={LEVEL_LABELS.level_1} items={grouped.level_1} />
        <OutlineColumn title={LEVEL_LABELS.level_2} items={grouped.level_2} />
        <OutlineColumn title={LEVEL_LABELS.level_3} items={grouped.level_3} />
      </div>

      {result ? (
        <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
          <section className="rounded-[28px] border border-black/10 bg-white/85 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
            <div className="flex items-center justify-between gap-4">
              <h3 className="text-lg font-semibold">风险标红</h3>
              <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                已收敛 {result.debate_rounds_completed} 轮
              </span>
            </div>
            <div className="mt-4 space-y-3">
              {result.risk_report.length > 0 ? (
                result.risk_report.map((issue) => (
                  <IssueCard
                    key={`${issue.source}-${issue.title}-${issue.detail}`}
                    issue={issue}
                  />
                ))
              ) : (
                <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                  当前主线骨架没有残留的高风险硬伤，可以继续细化。
                </div>
              )}
            </div>
          </section>

          <section className="rounded-[28px] border border-black/10 bg-white/85 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
            <h3 className="text-lg font-semibold">可直接执行的修补方案</h3>
            <div className="mt-4 space-y-3">
              {result.optimization_plan.map((item) => (
                <div
                  key={item}
                  className="rounded-3xl border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm leading-7 text-black/65"
                >
                  {item}
                </div>
              ))}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55">
                已综合人物一致性、剧情逻辑和节奏建议
              </span>
            </div>
          </section>
        </div>
      ) : null}
    </section>
  );
}
