"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  formatAiTaste,
  formatDateTime,
  formatScore,
  formatSignedDelta,
  QualityTrendChart,
  trendDirectionClassName,
  trendDirectionLabel,
} from "@/app/dashboard/_components/quality-trend";
import { apiFetchWithAuth } from "@/lib/api";
import type { DashboardProjectQualityTrend } from "@/types/api";

const CHAPTER_LIMIT_OPTIONS = [8, 24, 50] as const;

function chapterRiskLevel(
  overallScore: number | null,
  aiTasteScore: number | null,
): "risk" | "watch" | "healthy" {
  if (
    (typeof overallScore === "number" && overallScore < 0.75) ||
    (typeof aiTasteScore === "number" && aiTasteScore > 0.35)
  ) {
    return "risk";
  }
  if (
    (typeof overallScore === "number" && overallScore < 0.82) ||
    (typeof aiTasteScore === "number" && aiTasteScore > 0.25)
  ) {
    return "watch";
  }
  return "healthy";
}

function chapterRiskClassName(level: "risk" | "watch" | "healthy"): string {
  if (level === "risk") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (level === "watch") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

export default function ProjectQualityPage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;

  const [trend, setTrend] = useState<DashboardProjectQualityTrend | null>(null);
  const [chapterLimit, setChapterLimit] = useState<number>(24);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadTrend = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetchWithAuth<DashboardProjectQualityTrend>(
        `/api/v1/dashboard/projects/${projectId}/quality-trend?chapter_limit=${chapterLimit}`,
      );
      setTrend(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load project quality trend.",
      );
    } finally {
      setLoading(false);
    }
  }, [chapterLimit, projectId]);

  useEffect(() => {
    void loadTrend();
  }, [loadTrend]);

  const strongestChapter = trend?.strongest_chapter ?? null;
  const weakestChapter = trend?.weakest_chapter ?? null;
  const statusBreakdownEntries = Object.entries(trend?.status_breakdown ?? {});

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <section className="rounded-[2rem] border border-black/10 bg-[linear-gradient(135deg,rgba(250,246,239,0.98),rgba(240,234,225,0.92))] p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="text-sm uppercase tracking-[0.24em] text-copper">
                Project Quality Detail
              </p>
              <h1 className="mt-3 text-4xl font-semibold">
                {trend?.title ?? "项目质量趋势详情"}
              </h1>
              <p className="mt-3 text-sm leading-7 text-black/65">
                这不是摘要卡片，而是项目级质量剖面。这里会展开最近章节评分轨迹、风险点、强弱章节和可执行入口，方便你决定下一步该修哪里。
              </p>
              {trend ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  <span
                    className={`rounded-full border px-3 py-1 text-xs ${trendDirectionClassName(trend.trend_direction)}`}
                  >
                    {trendDirectionLabel(trend.trend_direction)}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    范围 Ch{trend.range_start_chapter_number ?? "-"} - Ch
                    {trend.range_end_chapter_number ?? "-"}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    展示 {trend.visible_chapter_count}/{trend.chapter_count} 章
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    角色 {trend.access_role}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    协作者 {trend.collaborator_count}
                  </span>
                  <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                    更新于 {formatDateTime(trend.updated_at)}
                  </span>
                </div>
              ) : null}
            </div>

            <div className="flex flex-wrap gap-3">
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href="/dashboard"
              >
                返回工作台
              </Link>
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href={`/dashboard/projects/${projectId}/chapters`}
              >
                章节工作区
              </Link>
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href={`/dashboard/projects/${projectId}/bible`}
              >
                Story Bible
              </Link>
              <Link
                className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm"
                href={`/dashboard/projects/${projectId}/collaborators`}
              >
                协作者
              </Link>
            </div>
          </div>
        </section>

        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <article className="rounded-3xl border border-black/10 bg-white/75 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">最新评分</p>
            <p className="mt-3 text-3xl font-semibold">
              {formatScore(trend?.latest_overall_score ?? null)}
            </p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/75 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">区间均分</p>
            <p className="mt-3 text-3xl font-semibold">
              {formatScore(trend?.average_overall_score ?? null)}
            </p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/75 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">评分变化</p>
            <p className="mt-3 text-3xl font-semibold">
              {formatSignedDelta(trend?.score_delta ?? null)}
            </p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/75 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">最新 AI 味</p>
            <p className="mt-3 text-3xl font-semibold">
              {formatAiTaste(trend?.latest_ai_taste_score ?? null)}
            </p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/75 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">区间均值 AI 味</p>
            <p className="mt-3 text-3xl font-semibold">
              {formatAiTaste(trend?.average_ai_taste_score ?? null)}
            </p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/75 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">覆盖率</p>
            <p className="mt-3 text-3xl font-semibold">
              {trend ? `${(trend.coverage_ratio * 100).toFixed(0)}%` : "-"}
            </p>
          </article>
        </section>

        <section className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold">趋势轨迹</h2>
              <p className="mt-2 text-sm leading-7 text-black/65">
                调整查看范围，观察这个项目最近一段时间的评分走向，而不是只看最后一个章节分数。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {CHAPTER_LIMIT_OPTIONS.map((limit) => (
                <button
                  key={limit}
                  className={`rounded-2xl border px-4 py-2 text-sm ${
                    chapterLimit === limit
                      ? "border-copper bg-[#f6ede3] text-copper"
                      : "border-black/10 bg-white text-black/70"
                  }`}
                  type="button"
                  onClick={() => setChapterLimit(limit)}
                >
                  最近 {limit} 章
                </button>
              ))}
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
                type="button"
                onClick={() => void loadTrend()}
              >
                刷新
              </button>
            </div>
          </div>

          {loading ? (
            <p className="mt-6 text-sm text-black/60">加载趋势详情中...</p>
          ) : (
            <div className="mt-6">
              <QualityTrendChart
                points={trend?.chapter_points ?? []}
                width={760}
                height={220}
              />
            </div>
          )}

          {trend ? (
            <div className="mt-6 flex flex-wrap gap-2">
              {trend.chapter_points.map((point) => {
                const riskLevel = chapterRiskLevel(
                  point.overall_score,
                  point.ai_taste_score,
                );
                return (
                  <span
                    key={point.chapter_id}
                    className={`rounded-full border px-3 py-1 text-xs ${chapterRiskClassName(
                      riskLevel,
                    )}`}
                  >
                    Ch{point.chapter_number} {formatScore(point.overall_score)}
                  </span>
                );
              })}
            </div>
          ) : null}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="grid gap-6">
            <section className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
              <h2 className="text-xl font-semibold">章节明细</h2>
              <p className="mt-2 text-sm leading-7 text-black/65">
                每个章节都给出当前状态、评分、AI 味和直接跳转入口，方便你按优先级进入编辑器处理。
              </p>

              {!loading && trend?.chapter_points.length === 0 ? (
                <p className="mt-6 text-sm leading-7 text-black/60">
                  当前区间还没有章节评分点。先完成一次章节评估或生成，趋势详情才会形成。
                </p>
              ) : null}

              <div className="mt-6 grid gap-4">
                {(trend?.chapter_points ?? []).map((point) => {
                  const riskLevel = chapterRiskLevel(
                    point.overall_score,
                    point.ai_taste_score,
                  );
                  return (
                    <article
                      key={point.chapter_id}
                      className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-5"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-xs uppercase tracking-[0.18em] text-copper">
                              Chapter {point.chapter_number}
                            </p>
                            <span
                              className={`rounded-full border px-3 py-1 text-xs ${chapterRiskClassName(
                                riskLevel,
                              )}`}
                            >
                              {riskLevel === "risk"
                                ? "高风险"
                                : riskLevel === "watch"
                                  ? "观察"
                                  : "健康"}
                            </span>
                          </div>
                          <h3 className="mt-2 text-lg font-semibold">
                            {point.title || `第 ${point.chapter_number} 章`}
                          </h3>
                          <p className="mt-2 text-sm text-black/65">
                            状态：{point.status} · 更新时间：{formatDateTime(point.updated_at)}
                          </p>
                        </div>
                        <Link
                          className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                          href={`/dashboard/editor/${point.chapter_id}`}
                        >
                          打开编辑器
                        </Link>
                      </div>

                      <div className="mt-4 grid gap-3 md:grid-cols-4">
                        <div className="rounded-2xl border border-black/10 bg-white p-3">
                          <p className="text-xs uppercase tracking-[0.16em] text-copper">
                            综合评分
                          </p>
                          <p className="mt-2 text-sm text-black/70">
                            {formatScore(point.overall_score)}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-black/10 bg-white p-3">
                          <p className="text-xs uppercase tracking-[0.16em] text-copper">
                            AI 味
                          </p>
                          <p className="mt-2 text-sm text-black/70">
                            {formatAiTaste(point.ai_taste_score)}
                          </p>
                        </div>
                        <div className="rounded-2xl border border-black/10 bg-white p-3">
                          <p className="text-xs uppercase tracking-[0.16em] text-copper">
                            词数
                          </p>
                          <p className="mt-2 text-sm text-black/70">{point.word_count}</p>
                        </div>
                        <div className="rounded-2xl border border-black/10 bg-white p-3">
                          <p className="text-xs uppercase tracking-[0.16em] text-copper">
                            风险判断
                          </p>
                          <p className="mt-2 text-sm text-black/70">
                            {riskLevel === "risk"
                              ? "需要优先处理"
                              : riskLevel === "watch"
                                ? "建议继续观察"
                                : "当前区间健康"}
                          </p>
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          </div>

          <div className="grid gap-6">
            <section className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
              <h2 className="text-xl font-semibold">区间摘要</h2>
              <div className="mt-6 grid gap-3">
                <article className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">
                    强势章节
                  </p>
                  <p className="mt-2 text-sm font-medium text-black/80">
                    {strongestChapter
                      ? `Ch${strongestChapter.chapter_number} · ${strongestChapter.title ?? `第 ${strongestChapter.chapter_number} 章`}`
                      : "暂无"}
                  </p>
                  <p className="mt-2 text-sm text-black/60">
                    评分 {formatScore(strongestChapter?.overall_score ?? null)}
                  </p>
                </article>

                <article className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">
                    薄弱章节
                  </p>
                  <p className="mt-2 text-sm font-medium text-black/80">
                    {weakestChapter
                      ? `Ch${weakestChapter.chapter_number} · ${weakestChapter.title ?? `第 ${weakestChapter.chapter_number} 章`}`
                      : "暂无"}
                  </p>
                  <p className="mt-2 text-sm text-black/60">
                    评分 {formatScore(weakestChapter?.overall_score ?? null)}
                  </p>
                </article>

                <article className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">
                    评审推进
                  </p>
                  <p className="mt-2 text-sm text-black/70">
                    Review 可用 {trend?.review_ready_chapters ?? 0} 章
                  </p>
                  <p className="mt-1 text-sm text-black/70">
                    Final 完成 {trend?.final_chapters ?? 0} 章
                  </p>
                </article>

                <article className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">
                    风险章节
                  </p>
                  <p className="mt-2 text-sm leading-7 text-black/70">
                    {trend && trend.risk_chapter_numbers.length > 0
                      ? trend.risk_chapter_numbers
                          .map((chapterNumber) => `Ch${chapterNumber}`)
                          .join(" / ")
                      : "当前区间没有高风险章节"}
                  </p>
                </article>
              </div>
            </section>

            <section className="rounded-3xl border border-black/10 bg-white/80 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
              <h2 className="text-xl font-semibold">状态分布</h2>
              <div className="mt-6 flex flex-wrap gap-3">
                {statusBreakdownEntries.length === 0 ? (
                  <p className="text-sm text-black/60">当前区间没有章节状态数据。</p>
                ) : (
                  statusBreakdownEntries.map(([status, count]) => (
                    <span
                      key={status}
                      className="rounded-full border border-black/10 bg-[#fbfaf5] px-4 py-2 text-sm text-black/70"
                    >
                      {status} · {count}
                    </span>
                  ))
                )}
              </div>
            </section>
          </div>
        </section>
      </div>
    </main>
  );
}
