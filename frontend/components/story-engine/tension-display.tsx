"use client";

import { useMemo } from "react";

interface TensionDisplayProps {
  tensionScore: number;
  tensionLevel: "low" | "moderate" | "high" | "critical";
  tensionCurve?: Array<{ position: number; tension_score: number; summary: string }>;
  chapterNumber?: number;
}

export function TensionDisplay({
  tensionScore,
  tensionLevel,
  tensionCurve = [],
  chapterNumber,
}: TensionDisplayProps) {
  const levelColor: Record<string, string> = {
    low: "text-green-500",
    moderate: "text-yellow-500",
    high: "text-orange-500",
    critical: "text-red-500",
  };

  const levelBg: Record<string, string> = {
    low: "bg-green-50",
    moderate: "bg-yellow-50",
    high: "bg-orange-50",
    critical: "bg-red-50",
  };

  const levelLabel: Record<string, string> = {
    low: "平缓",
    moderate: "适中",
    high: "紧张",
    critical: "高能",
  };

  const barWidth = Math.round(tensionScore * 100);

  return (
    <div className={`rounded-lg p-3 ${levelBg[tensionLevel]} border border-gray-200`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-gray-500">
          {chapterNumber != null ? `第 ${chapterNumber} 章` : "本章"}张力
        </span>
        <span className={`text-sm font-semibold ${levelColor[tensionLevel]}`}>
          {levelLabel[tensionLevel]}
        </span>
      </div>

      <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden mb-1">
        <div
          className={`absolute left-0 top-0 h-full rounded-full transition-all duration-500 ${levelColor[tensionLevel].replace("text-", "bg-")}`}
          style={{ width: `${barWidth}%` }}
        />
      </div>

      <div className="flex justify-between items-end h-16 gap-0.5">
        {tensionCurve.length > 0
          ? tensionCurve.map((point, i) => (
              <TensionBar
                key={i}
                score={point.tension_score}
                label={String(i + 1)}
                maxScore={1}
              />
            ))
          : Array.from({ length: 5 }, (_, i) => (
              <TensionBar
                key={i}
                score={tensionScore}
                label={String(i + 1)}
                maxScore={1}
              />
            ))}
      </div>

      {tensionCurve.length > 0 && (
        <div className="text-xs text-gray-400 text-center mt-1">
          场景张力曲线（{tensionCurve.length} 个场景）
        </div>
      )}
    </div>
  );
}

function TensionBar({
  score,
  label,
  maxScore,
}: {
  score: number;
  label: string;
  maxScore: number;
}) {
  const heightPct = maxScore > 0 ? (score / maxScore) * 100 : 0;
  const color =
    score >= 0.75 ? "bg-red-500" : score >= 0.5 ? "bg-orange-400" : score >= 0.25 ? "bg-yellow-400" : "bg-green-400";

  return (
    <div className="flex-1 flex flex-col items-center justify-end gap-0.5">
      <div className="w-full relative" style={{ height: "36px" }}>
        <div
          className={`absolute bottom-0 w-full rounded-sm ${color} opacity-70 transition-all`}
          style={{ height: `${heightPct}%` }}
        />
      </div>
      <span className="text-[9px] text-gray-400">{label}</span>
    </div>
  );
}
