"use client";

import type { DashboardProjectTrendPoint } from "@/types/api";

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
  }).format(date);
}

export function formatScore(value: number | null): string {
  if (typeof value !== "number") {
    return "-";
  }
  return `${(value * 10).toFixed(1)}/10`;
}

export function formatAiTaste(value: number | null): string {
  if (typeof value !== "number") {
    return "-";
  }
  return value.toFixed(2);
}

export function formatSignedDelta(value: number | null): string {
  if (typeof value !== "number") {
    return "-";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 10).toFixed(1)}`;
}

export function trendDirectionLabel(direction: string): string {
  if (direction === "improving") {
    return "上升";
  }
  if (direction === "declining") {
    return "走低";
  }
  if (direction === "stable") {
    return "持平";
  }
  return "数据不足";
}

export function trendDirectionClassName(direction: string): string {
  if (direction === "improving") {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }
  if (direction === "declining") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (direction === "stable") {
    return "border-sky-200 bg-sky-50 text-sky-700";
  }
  return "border-black/10 bg-white text-black/55";
}

export function buildTrendChartPoints(
  points: DashboardProjectTrendPoint[],
  width: number,
  height: number,
) {
  const padding = 10;
  const usableWidth = width - padding * 2;
  const usableHeight = height - padding * 2;
  const chartPoints = points
    .map((point, index) => {
      if (typeof point.overall_score !== "number") {
        return null;
      }
      const x =
        padding +
        (points.length <= 1
          ? usableWidth / 2
          : (index * usableWidth) / (points.length - 1));
      const y = padding + (1 - point.overall_score) * usableHeight;
      return {
        chapterNumber: point.chapter_number,
        score: point.overall_score,
        x,
        y,
      };
    })
    .filter(
      (
        point,
      ): point is { chapterNumber: number; score: number; x: number; y: number } =>
        point !== null,
    );

  const path = chartPoints
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`)
    .join(" ");

  return {
    path,
    chartPoints,
  };
}

export function QualityTrendChart({
  points,
  width = 320,
  height = 120,
}: {
  points: DashboardProjectTrendPoint[];
  width?: number;
  height?: number;
}) {
  const { path, chartPoints } = buildTrendChartPoints(points, width, height);

  if (chartPoints.length === 0) {
    return (
      <div
        className="flex items-center justify-center rounded-2xl border border-dashed border-black/10 bg-[#fbfaf5] text-sm text-black/50"
        style={{ height }}
      >
        还没有可绘制的评分点
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-black/10 bg-[#fbfaf5] p-3">
      <svg
        className="w-full"
        style={{ height }}
        viewBox={`0 0 ${width} ${height}`}
        fill="none"
        role="img"
      >
        {[0.25, 0.5, 0.75].map((tick) => {
          const y = 10 + (1 - tick) * (height - 20);
          return (
            <line
              key={tick}
              x1="10"
              x2={String(width - 10)}
              y1={String(y)}
              y2={String(y)}
              stroke="rgba(18,24,27,0.10)"
              strokeDasharray="3 5"
            />
          );
        })}
        {path ? (
          <path
            d={path}
            stroke="#b26d3a"
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}
        {chartPoints.map((point) => (
          <g key={point.chapterNumber}>
            <circle cx={point.x} cy={point.y} r="4" fill="#11181c" />
            <text
              x={point.x}
              y={height - 4}
              textAnchor="middle"
              fontSize="10"
              fill="rgba(17,24,28,0.55)"
            >
              {point.chapterNumber}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}
