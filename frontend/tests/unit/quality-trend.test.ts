import { describe, expect, it } from "vitest";

import {
  buildTrendChartPoints,
  formatAiTaste,
  formatScore,
  formatSignedDelta,
  trendDirectionClassName,
  trendDirectionLabel,
} from "@/app/dashboard/_components/quality-trend";


describe("quality trend helpers", () => {
  it("formats score-like values for display", () => {
    expect(formatScore(0.82)).toBe("8.2/10");
    expect(formatAiTaste(0.237)).toBe("0.24");
    expect(formatSignedDelta(0.11)).toBe("+1.1");
    expect(formatSignedDelta(-0.07)).toBe("-0.7");
    expect(formatScore(null)).toBe("-");
  });

  it("maps trend directions to labels and class names", () => {
    expect(trendDirectionLabel("improving")).toBe("上升");
    expect(trendDirectionLabel("declining")).toBe("走低");
    expect(trendDirectionLabel("stable")).toBe("持平");
    expect(trendDirectionLabel("unknown")).toBe("数据不足");
    expect(trendDirectionClassName("improving")).toContain("emerald");
    expect(trendDirectionClassName("declining")).toContain("amber");
    expect(trendDirectionClassName("stable")).toContain("sky");
  });

  it("builds chart points only for numeric scores", () => {
    const { path, chartPoints } = buildTrendChartPoints(
      [
        {
          chapter_id: "ch-1",
          chapter_number: 1,
          title: "第一章",
          status: "draft",
          overall_score: 0.9,
          ai_taste_score: null,
          word_count: 1800,
          updated_at: "2026-04-04T10:00:00Z",
        },
        {
          chapter_id: "ch-2",
          chapter_number: 2,
          title: "第二章",
          status: "draft",
          overall_score: null,
          ai_taste_score: null,
          word_count: 2000,
          updated_at: "2026-04-04T11:00:00Z",
        },
        {
          chapter_id: "ch-3",
          chapter_number: 3,
          title: "第三章",
          status: "review_ready",
          overall_score: 0.6,
          ai_taste_score: null,
          word_count: 2200,
          updated_at: "2026-04-04T12:00:00Z",
        },
      ],
      320,
      120,
    );

    expect(chartPoints).toHaveLength(2);
    expect(chartPoints[0].chapterNumber).toBe(1);
    expect(chartPoints[1].chapterNumber).toBe(3);
    expect(path).toContain("M");
    expect(path).toContain("L");
  });
});
