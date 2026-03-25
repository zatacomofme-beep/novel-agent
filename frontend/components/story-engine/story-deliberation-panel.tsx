"use client";

import type { StoryEngineDeliberationRound } from "@/types/api";

type StoryDeliberationPanelProps = {
  title: string;
  description: string;
  rounds: StoryEngineDeliberationRound[];
  emptyText: string;
};

const STANCE_LABELS: Record<string, string> = {
  review: "先看一轮",
  challenge: "专门挑刺",
  revise: "补结构",
  arbitrate: "最终裁决",
  anchor: "顺手记下",
};

const ISSUE_TONES: Record<string, string> = {
  critical: "border-red-200 bg-red-50 text-red-700",
  high: "border-orange-200 bg-orange-50 text-orange-700",
  medium: "border-amber-200 bg-amber-50 text-amber-700",
  low: "border-sky-200 bg-sky-50 text-sky-700",
};

export function StoryDeliberationPanel({
  title,
  description,
  rounds,
  emptyText,
}: StoryDeliberationPanelProps) {
  return (
    <details className="rounded-[30px] border border-black/10 bg-white/82 p-5 shadow-[0_18px_40px_rgba(16,20,23,0.05)]">
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-copper">查看优化依据</p>
          <h3 className="mt-2 text-lg font-semibold">{title}</h3>
          <p className="mt-2 text-sm leading-7 text-black/58">{description}</p>
        </div>
        <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
          {rounds.length > 0 ? `${rounds.length} 轮` : "暂无"}
        </span>
      </summary>

      <div className="mt-5 space-y-4">
        {rounds.length > 0 ? (
          rounds.map((round) => (
            <article
              key={`${round.round_number}-${round.title}`}
              className="rounded-[28px] border border-black/10 bg-[#fbfaf5] p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.16em] text-copper">
                    第 {round.round_number} 轮
                  </p>
                  <h4 className="mt-2 text-base font-semibold">{round.title}</h4>
                  <p className="mt-2 text-sm leading-7 text-black/60">{round.summary}</p>
                </div>
              </div>

              {round.resolution ? (
                <div className="mt-3 rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm leading-7 text-black/62">
                  {round.resolution}
                </div>
              ) : null}

              <div className="mt-4 space-y-3">
                {round.entries.map((entry) => (
                  <div
                    key={`${round.round_number}-${entry.actor_key}-${entry.actor_label}`}
                    className="rounded-3xl border border-black/10 bg-white p-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-black/78">{entry.actor_label}</p>
                        <p className="mt-1 text-xs text-black/48">{STANCE_LABELS[entry.stance] ?? entry.role}</p>
                      </div>
                      <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                        {entry.issues.length} 个关注点
                      </span>
                    </div>

                    <p className="mt-3 text-sm leading-7 text-black/64">{entry.summary}</p>

                    {entry.evidence.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {entry.evidence.map((item) => (
                          <span
                            key={`${entry.actor_key}-${item}`}
                            className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55"
                          >
                            {item}
                          </span>
                        ))}
                      </div>
                    ) : null}

                    {entry.issues.length > 0 ? (
                      <div className="mt-3 space-y-2">
                        {entry.issues.map((issue) => (
                          <div
                            key={`${entry.actor_key}-${issue.title}-${issue.detail}`}
                            className={`rounded-2xl border px-3 py-3 text-sm leading-7 ${
                              ISSUE_TONES[issue.severity] ?? ISSUE_TONES.low
                            }`}
                          >
                            <p className="font-semibold">{issue.title}</p>
                            <p className="mt-1">{issue.detail}</p>
                          </div>
                        ))}
                      </div>
                    ) : null}

                    {entry.actions.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {entry.actions.map((action) => (
                          <span
                            key={`${entry.actor_key}-${action}`}
                            className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-1 text-xs text-copper"
                          >
                            {action}
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </article>
          ))
        ) : (
          <div className="rounded-3xl border border-dashed border-black/10 bg-[#fbfaf5] px-4 py-5 text-sm leading-7 text-black/48">
            {emptyText}
          </div>
        )}
      </div>
    </details>
  );
}
