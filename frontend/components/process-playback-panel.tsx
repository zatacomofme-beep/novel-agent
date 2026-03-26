"use client";

import Link from "next/link";

import { formatDateTime } from "@/components/editor/formatters";

export type ProcessPlaybackStatus = "queued" | "running" | "succeeded" | "failed" | "paused";

export type ProcessPlaybackStep = {
  id: string;
  label: string;
  detail?: string | null;
  status: ProcessPlaybackStatus;
  createdAt?: string | null;
};

export type ProcessPlaybackItem = {
  id: string;
  label: string;
  title: string;
  summary: string;
  status: ProcessPlaybackStatus;
  statusLabel?: string | null;
  progress?: number | null;
  updatedAt?: string | null;
  badges?: string[];
  steps: ProcessPlaybackStep[];
  actionLabel?: string | null;
  actionHref?: string | null;
  onAction?: (() => void) | null;
};

type ProcessPlaybackPanelProps = {
  title: string;
  subtitle?: string;
  items: ProcessPlaybackItem[];
  emptyTitle: string;
  emptyDescription: string;
};

const STATUS_LABELS: Record<ProcessPlaybackStatus, string> = {
  queued: "已收下",
  running: "处理中",
  succeeded: "已完成",
  failed: "没跑通",
  paused: "已停住",
};

const STATUS_TONES: Record<ProcessPlaybackStatus, string> = {
  queued: "border-black/10 bg-white text-black/62",
  running: "border-sky-200 bg-sky-50 text-sky-700",
  succeeded: "border-emerald-200 bg-emerald-50 text-emerald-700",
  failed: "border-red-200 bg-red-50 text-red-700",
  paused: "border-amber-200 bg-amber-50 text-amber-700",
};

function progressLabel(progress: number | null | undefined): string | null {
  if (typeof progress !== "number" || Number.isNaN(progress)) {
    return null;
  }
  return `${Math.max(0, Math.min(100, Math.round(progress)))}%`;
}

export function ProcessPlaybackPanel({
  title,
  subtitle,
  items,
  emptyTitle,
  emptyDescription,
}: ProcessPlaybackPanelProps) {
  return (
    <section className="rounded-[32px] border border-black/10 bg-white/82 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-copper">最近过程</p>
          <h2 className="mt-2 text-xl font-semibold">{title}</h2>
          {subtitle ? (
            <p className="mt-2 text-sm leading-7 text-black/58">{subtitle}</p>
          ) : null}
        </div>
        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
          {items.length} 条
        </span>
      </div>

      {items.length === 0 ? (
        <div className="mt-5 rounded-[24px] border border-black/10 bg-[#fbfaf5] px-5 py-4">
          <p className="text-sm font-semibold text-black/82">{emptyTitle}</p>
          <p className="mt-2 text-sm leading-7 text-black/58">{emptyDescription}</p>
        </div>
      ) : (
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {items.map((item) => {
            const normalizedProgress = Math.max(
              0,
              Math.min(100, Math.round(item.progress ?? 0)),
            );
            const resolvedStatusLabel =
              item.statusLabel?.trim() || STATUS_LABELS[item.status];

            return (
              <article
                key={item.id}
                className="rounded-[24px] border border-black/10 bg-[#fbfaf5] p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.18em] text-copper">{item.label}</p>
                    <h3 className="mt-2 text-lg font-semibold text-black/82">{item.title}</h3>
                    <p className="mt-2 text-sm leading-7 text-black/62">{item.summary}</p>
                  </div>
                  <span
                    className={`rounded-full border px-3 py-1 text-xs ${STATUS_TONES[item.status]}`}
                  >
                    {resolvedStatusLabel}
                  </span>
                </div>

                {typeof item.progress === "number" ? (
                  <div className="mt-4">
                    <div className="h-2 rounded-full bg-white">
                      <div
                        className={`h-2 rounded-full transition-all ${
                          item.status === "failed"
                            ? "bg-red-400"
                            : item.status === "succeeded"
                              ? "bg-emerald-500"
                              : item.status === "paused"
                                ? "bg-amber-400"
                                : "bg-sky-500"
                        }`}
                        style={{ width: `${normalizedProgress}%` }}
                      />
                    </div>
                    <p className="mt-2 text-xs text-black/48">
                      当前进度 {progressLabel(item.progress)}
                    </p>
                  </div>
                ) : null}

                {item.badges && item.badges.length > 0 ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {item.badges.map((badge) => (
                      <span
                        key={`${item.id}:${badge}`}
                        className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55"
                      >
                        {badge}
                      </span>
                    ))}
                  </div>
                ) : null}

                <div className="mt-4 space-y-2">
                  {item.steps.slice(0, 4).map((step) => (
                    <div
                      key={step.id}
                      className="rounded-[18px] border border-black/10 bg-white px-4 py-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-sm font-medium text-black/78">{step.label}</p>
                        <span
                          className={`rounded-full border px-3 py-1 text-[11px] ${
                            STATUS_TONES[step.status]
                          }`}
                        >
                          {STATUS_LABELS[step.status]}
                        </span>
                      </div>
                      {step.detail ? (
                        <p className="mt-2 text-xs leading-6 text-black/56">{step.detail}</p>
                      ) : null}
                      {step.createdAt ? (
                        <p className="mt-2 text-[11px] text-black/42">
                          {formatDateTime(step.createdAt)}
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-3">
                  {item.updatedAt ? (
                    <span className="text-xs text-black/45">
                      更新于 {formatDateTime(item.updatedAt)}
                    </span>
                  ) : null}
                  {item.actionHref && item.actionLabel ? (
                    <Link
                      className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                      href={item.actionHref}
                    >
                      {item.actionLabel}
                    </Link>
                  ) : null}
                  {!item.actionHref && item.onAction && item.actionLabel ? (
                    <button
                      className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                      onClick={item.onAction}
                      type="button"
                    >
                      {item.actionLabel}
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
