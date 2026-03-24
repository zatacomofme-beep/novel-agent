"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import {
  formatAiTaste,
  formatDateTime,
  formatScore,
  formatSignedDelta,
  QualityTrendChart,
  trendDirectionClassName,
  trendDirectionLabel,
} from "@/app/dashboard/_components/quality-trend";
import { apiFetchWithAuth, downloadWithAuth } from "@/lib/api";
import { clearAuthSession, loadAuthSession } from "@/lib/auth";
import type {
  DashboardOverview,
  DashboardProjectQualityTrend,
  Project,
  User,
} from "@/types/api";

function QualityTrendCard({ trend }: { trend: DashboardProjectQualityTrend }) {
  return (
    <article className="rounded-3xl border border-black/10 bg-white/80 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.05)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold">{trend.title}</h3>
          <p className="mt-2 text-sm text-black/60">
            最近更新 {formatDateTime(trend.updated_at)}
          </p>
          <p className="mt-1 text-sm text-black/50">
            已评估 {trend.evaluated_chapter_count}/{trend.chapter_count} 章
          </p>
          <p className="mt-1 text-sm text-black/50">
            当前身份：{trend.access_role}
            {trend.owner_email ? ` · ${trend.owner_email}` : ""}
          </p>
        </div>
        <span
          className={`rounded-full border px-3 py-1 text-xs ${trendDirectionClassName(trend.trend_direction)}`}
        >
          {trendDirectionLabel(trend.trend_direction)}
        </span>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
          <p className="text-xs uppercase tracking-[0.16em] text-copper">最新评分</p>
          <p className="mt-2 text-sm text-black/70">{formatScore(trend.latest_overall_score)}</p>
        </div>
        <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
          <p className="text-xs uppercase tracking-[0.16em] text-copper">趋势变化</p>
          <p className="mt-2 text-sm text-black/70">{formatSignedDelta(trend.score_delta)}</p>
        </div>
        <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
          <p className="text-xs uppercase tracking-[0.16em] text-copper">机械感</p>
          <p className="mt-2 text-sm text-black/70">{formatAiTaste(trend.latest_ai_taste_score)}</p>
        </div>
        <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
          <p className="text-xs uppercase tracking-[0.16em] text-copper">覆盖率</p>
          <p className="mt-2 text-sm text-black/70">{(trend.coverage_ratio * 100).toFixed(0)}%</p>
        </div>
      </div>

      <div className="mt-4">
        <QualityTrendChart points={trend.chapter_points} />
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
          协作者 {trend.collaborator_count}
        </span>
        {trend.chapter_points.map((point) => (
          <span
            key={point.chapter_id}
            className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60"
          >
            Ch{point.chapter_number} {formatScore(point.overall_score)}
          </span>
        ))}
      </div>

      {trend.risk_chapter_numbers.length > 0 ? (
        <p className="mt-4 text-sm leading-7 text-amber-700">
          重点回看章节：{trend.risk_chapter_numbers.map((value) => `Ch${value}`).join(" / ")}
        </p>
      ) : (
        <p className="mt-4 text-sm leading-7 text-emerald-700">
          最近趋势窗口内没有高风险章节。
        </p>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <Link
          className="rounded-2xl border border-black/10 bg-[#f6f0e6] px-3 py-2 text-sm font-medium"
          href={`/dashboard/projects/${trend.project_id}/story-room`}
        >
          进入故事工作台
        </Link>
      </div>
    </article>
  );
}

const preferenceValueLabels: Record<string, string> = {
  precise: "精确克制",
  lyrical: "抒情流动",
  sharp: "冷峻锋利",
  close_third: "贴身第三人称",
  omniscient: "多点俯瞰",
  first_person: "第一人称",
  fast: "快推进",
  balanced: "平衡",
  slow_burn: "慢燃积压",
  dialogue_forward: "对话驱动",
  narration_heavy: "叙述主导",
  restrained: "克制蓄压",
  high_tension: "高压逼近",
  minimal: "稀疏点染",
  focused: "重点锚点",
  immersive: "沉浸细节",
};

const recentTaskTypeLabels: Record<string, string> = {
  chapter_generation: "续写下一章",
  "entity_generation.characters": "补几个人物",
  "entity_generation.supporting": "补几个配角",
  "entity_generation.items": "补几件物品",
  "entity_generation.locations": "补几个地点",
  "entity_generation.factions": "补一个势力",
  "entity_generation.plot_threads": "补几条剧情线",
};

const recentTaskStatusLabels: Record<string, string> = {
  queued: "排队中",
  running: "处理中",
  succeeded: "已完成",
  failed: "已失败",
};

function formatRecentTaskType(taskType: string): string {
  return recentTaskTypeLabels[taskType] ?? taskType.replaceAll(".", " / ");
}

function formatRecentTaskStatus(status: string): string {
  return recentTaskStatusLabels[status] ?? status;
}

export default function DashboardPage() {
  const router = useRouter();
  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [exportingKey, setExportingKey] = useState<string | null>(null);

  useEffect(() => {
    const session = loadAuthSession();
    if (!session) {
      setLoading(false);
      return;
    }
    setCurrentUser(session.user);
    void fetchOverview();
  }, []);

  async function fetchOverview() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiFetchWithAuth<DashboardOverview>("/api/v1/dashboard/overview");
      setOverview(data);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to load dashboard overview.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreating(true);
    setError(null);
    try {
      const createdProject = await apiFetchWithAuth<Project>("/api/v1/projects", {
        method: "POST",
        body: JSON.stringify({
          title,
          genre: genre || null,
          status: "draft",
        }),
      });
      setTitle("");
      setGenre("");
      router.push(`/dashboard/projects/${createdProject.id}/story-room`);
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to create project.",
      );
    } finally {
      setCreating(false);
    }
  }

  function handleLogout() {
    clearAuthSession();
    setCurrentUser(null);
    setOverview(null);
  }

  async function handleExportProject(projectId: string, format: "md" | "txt") {
    setExportingKey(`${projectId}:${format}`);
    setError(null);
    try {
      await downloadWithAuth(`/api/v1/projects/${projectId}/export?format=${format}`);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Failed to export project.",
      );
    } finally {
      setExportingKey(null);
    }
  }

  if (!currentUser) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <div className="max-w-xl rounded-3xl border border-black/10 bg-white/75 p-8 text-center shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <p className="text-sm uppercase tracking-[0.24em] text-copper">
            项目页
          </p>
          <h1 className="mt-3 text-3xl font-semibold">尚未登录</h1>
          <p className="mt-4 text-sm leading-7 text-black/65">
            登录后就能进入项目页，继续写正文、看终稿对比和自动沉淀设定。
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Link
              className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper"
              href="/login"
            >
              去登录
            </Link>
            <Link
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium"
              href="/register"
            >
              去注册
            </Link>
          </div>
        </div>
      </main>
    );
  }

  const projectSummaries = overview?.project_summaries ?? [];
  const qualityTrends = overview?.project_quality_trends ?? [];
  const recentTasks = overview?.recent_tasks ?? [];
  const preferenceProfile = overview?.preference_profile ?? null;

  return (
    <main className="min-h-screen px-6 py-10">
      <div className="mx-auto flex max-w-7xl flex-col gap-8">
        <section className="flex flex-col gap-4 rounded-3xl border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] backdrop-blur md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.24em] text-copper">
              项目页
            </p>
            <h1 className="mt-3 text-4xl font-semibold">项目工作台</h1>
            <p className="mt-3 text-sm leading-7 text-black/65">
              当前登录用户：{currentUser.email}
              {" "}
              这一页只负责三件事：开新项目、看最近进度、回到正在写的故事工作台。
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium"
              onClick={handleLogout}
              type="button"
            >
              退出登录
            </button>
          </div>
        </section>

        {error ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">项目数</p>
            <p className="mt-3 text-3xl font-semibold">{overview?.total_projects ?? 0}</p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">章节数</p>
            <p className="mt-3 text-3xl font-semibold">{overview?.total_chapters ?? 0}</p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">总词数</p>
            <p className="mt-3 text-3xl font-semibold">{overview?.total_words ?? 0}</p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">活跃任务</p>
            <p className="mt-3 text-3xl font-semibold">{overview?.active_task_count ?? 0}</p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">待收口章节</p>
            <p className="mt-3 text-3xl font-semibold">{overview?.review_ready_chapters ?? 0}</p>
          </article>
          <article className="rounded-3xl border border-black/10 bg-white/70 p-5 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <p className="text-sm text-black/55">平均机械感</p>
            <p className="mt-3 text-3xl font-semibold">
              {formatAiTaste(overview?.average_ai_taste_score ?? null)}
            </p>
          </article>
        </section>

        <section className="rounded-3xl border border-black/10 bg-white/75 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold">最近写作走势</h2>
              <p className="mt-2 text-sm leading-7 text-black/65">
                这里按章节顺序展示最近的写作走势，方便你快速判断哪本书在抬升、哪本书需要回头补修。
              </p>
            </div>
            <button
              className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
              type="button"
              onClick={() => void fetchOverview()}
            >
              刷新趋势
            </button>
          </div>

          {loading ? (
            <p className="mt-6 text-sm text-black/60">加载趋势视图中...</p>
          ) : null}

          {!loading && qualityTrends.length === 0 ? (
            <p className="mt-6 text-sm leading-7 text-black/60">
              还没有可展示的趋势。先创建章节并完成一次评估或生成，项目评分轨迹才会形成。
            </p>
          ) : null}

          <div className="mt-6 grid gap-4 xl:grid-cols-2">
            {qualityTrends.map((trend) => (
              <QualityTrendCard key={trend.project_id} trend={trend} />
            ))}
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[360px_1fr]">
          <div className="grid gap-6">
            <form
              className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]"
              onSubmit={handleCreate}
            >
              <h2 className="text-xl font-semibold">创建项目</h2>
              <p className="mt-2 text-sm leading-7 text-black/65">
                新建项目后会直接进入故事工作台，从脑洞压大纲、正文创作到设定沉淀都在同一处完成。
              </p>

              <div className="mt-6 flex flex-col gap-4">
                <label className="flex flex-col gap-2 text-sm">
                  项目标题
                  <input
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    required
                  />
                </label>

                <label className="flex flex-col gap-2 text-sm">
                  类型
                  <input
                    className="rounded-2xl border border-black/10 bg-white px-4 py-3 outline-none transition focus:border-copper"
                    value={genre}
                    onChange={(event) => setGenre(event.target.value)}
                    placeholder="科幻 / 悬疑 / 奇幻..."
                  />
                </label>
              </div>

              <button
                className="mt-6 rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper transition hover:bg-copper disabled:cursor-not-allowed disabled:opacity-60"
                type="submit"
                disabled={creating}
              >
                {creating ? "创建中..." : "创建项目"}
              </button>
            </form>

            <section className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold">系统记住的写法</h2>
                  <p className="mt-2 text-sm leading-7 text-black/65">
                    这里显示系统已经学到的写作倾向。它会自动影响后续起稿和优化，你不用再单独切出去配置。
                  </p>
                </div>
              </div>

              {!preferenceProfile ? (
                <p className="mt-4 text-sm text-black/60">
                  正在整理你的写作习惯...
                </p>
              ) : (
                <>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs text-emerald-700">
                      完成度 {(preferenceProfile.completion_score * 100).toFixed(0)}%
                    </span>
                    {preferenceProfile.active_template ? (
                      <span className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-1 text-xs text-copper">
                        风格底稿 {preferenceProfile.active_template.name}
                      </span>
                    ) : null}
                    <span className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-1 text-xs text-copper">
                      已观察 {preferenceProfile.learning_snapshot.observation_count} 次
                    </span>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                      文风 {preferenceValueLabels[preferenceProfile.prose_style] ?? preferenceProfile.prose_style}
                    </span>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                      视角 {preferenceValueLabels[preferenceProfile.narrative_mode] ?? preferenceProfile.narrative_mode}
                    </span>
                    <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/65">
                      节奏 {preferenceValueLabels[preferenceProfile.pacing_preference] ?? preferenceProfile.pacing_preference}
                    </span>
                  </div>

                  {preferenceProfile.favored_elements.length > 0 ? (
                    <p className="mt-4 text-sm leading-7 text-black/70">
                      偏爱元素：{preferenceProfile.favored_elements.join(" / ")}
                    </p>
                  ) : null}

                  {preferenceProfile.learning_snapshot.summary ? (
                    <p className="mt-3 text-sm leading-7 text-black/70">
                      当前判断：{preferenceProfile.learning_snapshot.summary}
                    </p>
                  ) : null}

                  {preferenceProfile.active_template ? (
                    <p className="mt-3 text-sm leading-7 text-black/70">
                      当前风格底稿：{preferenceProfile.active_template.name} / {preferenceProfile.active_template.tagline}
                    </p>
                  ) : null}

                  {preferenceProfile.custom_style_notes ? (
                    <p className="mt-3 text-sm leading-7 text-black/70">
                      备注：{preferenceProfile.custom_style_notes}
                    </p>
                  ) : (
                    <p className="mt-3 text-sm leading-7 text-black/55">
                      还没有额外风格备注，系统会先按当前已观察到的写法来收束文风。
                    </p>
                  )}
                </>
              )}
            </section>

            <section className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-xl font-semibold">最近任务</h2>
                <button
                  className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm"
                  type="button"
                  onClick={() => void fetchOverview()}
                >
                  刷新
                </button>
              </div>

              {loading ? (
                <p className="mt-4 text-sm text-black/60">加载任务概览中...</p>
              ) : null}

              {!loading && recentTasks.length === 0 ? (
                <p className="mt-4 text-sm leading-7 text-black/60">
                  暂时没有任务记录。创建章节并发起生成后，这里会显示最近的运行状态。
                </p>
              ) : null}

              <div className="mt-4 grid gap-3">
                {recentTasks.map((task) => (
                  <article
                    key={task.task_id}
                    className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.16em] text-copper">
                          {formatRecentTaskType(task.task_type)}
                        </p>
                        <p className="mt-2 text-sm leading-7 text-black/75">
                          {task.message ?? "No task message"}
                        </p>
                      </div>
                      <div className="text-right text-xs text-black/50">
                        <p>{formatRecentTaskStatus(task.status)}</p>
                        <p className="mt-1">{task.progress}%</p>
                      </div>
                    </div>
                    <p className="mt-3 text-xs text-black/45">
                      更新于 {formatDateTime(task.updated_at)}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          </div>

          <section className="rounded-3xl border border-black/10 bg-white/70 p-6 shadow-[0_18px_50px_rgba(16,20,23,0.06)]">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">项目矩阵</h2>
                <p className="mt-2 text-sm leading-7 text-black/65">
                  项目卡片现在不仅显示基础信息，还显示章节状态、质量均值、风险章节和活跃任务数量。
                </p>
              </div>
              <button
                className="rounded-2xl border border-black/10 bg-white px-4 py-2 text-sm"
                type="button"
                onClick={() => void fetchOverview()}
              >
                刷新
              </button>
            </div>

            {loading ? (
              <p className="mt-6 text-sm text-black/60">加载项目概览中...</p>
            ) : null}

            {!loading && projectSummaries.length === 0 ? (
              <p className="mt-6 text-sm leading-7 text-black/60">
                还没有项目。先创建一个小说项目，工作台会自动开始汇总它的状态。
              </p>
            ) : null}

            <div className="mt-6 grid gap-4">
              {projectSummaries.map((project) => (
                <article
                  key={project.project_id}
                  className="rounded-2xl border border-black/10 bg-white/80 p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-lg font-semibold">{project.title}</h3>
                      <p className="mt-2 text-sm text-black/65">
                        类型：{project.genre ?? "未设置"}
                      </p>
                      <p className="mt-1 text-sm text-black/65">
                        状态：{project.status}
                      </p>
                      <p className="mt-1 text-sm text-black/45">
                        更新：{formatDateTime(project.updated_at)}
                      </p>
                      <p className="mt-1 text-sm text-black/45">
                        主理人：{project.owner_email ?? "当前账号"}
                      </p>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <span className="rounded-full bg-paper px-3 py-1 text-xs uppercase tracking-[0.18em] text-copper">
                        章节 {project.chapter_count}
                      </span>
                      <span
                        className={`rounded-full border px-3 py-1 text-xs ${trendDirectionClassName(project.trend_direction)}`}
                      >
                        {trendDirectionLabel(project.trend_direction)}
                      </span>
                      <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                        {project.access_role}
                      </span>
                      <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                        待收口 {project.review_ready_chapters}
                      </span>
                      <span className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/60">
                        待回看 {project.risk_chapter_count}
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 grid gap-3 md:grid-cols-5">
                    <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">
                        词数
                      </p>
                      <p className="mt-2 text-sm text-black/70">{project.word_count}</p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">
                        终稿
                      </p>
                      <p className="mt-2 text-sm text-black/70">{project.final_chapters}</p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">
                        活跃任务
                      </p>
                      <p className="mt-2 text-sm text-black/70">{project.active_task_count}</p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">
                        平均评分
                      </p>
                      <p className="mt-2 text-sm text-black/70">
                        {formatScore(project.average_overall_score)}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">
                        平均机械感
                      </p>
                      <p className="mt-2 text-sm text-black/70">
                        {formatAiTaste(project.average_ai_taste_score)}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3 md:col-span-5">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">
                        协作信息
                      </p>
                      <p className="mt-2 text-sm text-black/70">
                        当前角色 {project.access_role}
                        {" · "}
                        协作者 {project.collaborator_count}
                      </p>
                    </div>
                    <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3 md:col-span-5">
                      <p className="text-xs uppercase tracking-[0.16em] text-copper">
                        最近趋势
                      </p>
                      <p className="mt-2 text-sm text-black/70">
                        {trendDirectionLabel(project.trend_direction)}
                        {" · "}
                        评分变化 {formatSignedDelta(project.score_delta)}
                      </p>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link
                      className="rounded-2xl border border-black/10 bg-[#f6f0e6] px-3 py-2 text-sm font-medium"
                      href={`/dashboard/projects/${project.project_id}/story-room`}
                    >
                      进入故事工作台
                    </Link>
                    <button
                      className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                      type="button"
                      onClick={() => void handleExportProject(project.project_id, "md")}
                      disabled={exportingKey === `${project.project_id}:md`}
                    >
                      {exportingKey === `${project.project_id}:md` ? "导出中..." : "导出项目 MD"}
                    </button>
                    <button
                      className="rounded-2xl border border-black/10 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
                      type="button"
                      onClick={() => void handleExportProject(project.project_id, "txt")}
                      disabled={exportingKey === `${project.project_id}:txt`}
                    >
                      {exportingKey === `${project.project_id}:txt` ? "导出中..." : "导出项目 TXT"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </section>
      </div>
    </main>
  );
}
