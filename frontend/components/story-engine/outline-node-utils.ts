"use client";

export type OutlineNode = {
  key: string;
  index: number;
  title: string;
  summary: string;
};

const OUTLINE_BULLET_PATTERN =
  /^(?:\d+[.、)|．]|[一二三四五六七八九十]+[、.)]|[-*•·]|（\d+）|\(\d+\))\s*/;

export function hashText(value: string): string {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash.toString(16);
}

function chunkSegments(items: string[], maxCount = 5): string[] {
  if (items.length <= maxCount) {
    return items;
  }
  const chunkSize = Math.ceil(items.length / maxCount);
  const result: string[] = [];
  for (let index = 0; index < items.length; index += chunkSize) {
    result.push(items.slice(index, index + chunkSize).join(" "));
  }
  return result;
}

function splitOutlineSegments(outlineContent: string): string[] {
  const normalized = outlineContent.replace(/\r\n/g, "\n").trim();
  if (!normalized) {
    return [];
  }

  const lines = normalized
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

  const lineSegments: string[] = [];
  lines.forEach((line) => {
    const cleanedLine = line.replace(OUTLINE_BULLET_PATTERN, "").trim();
    if (!cleanedLine) {
      return;
    }

    const shouldOpenNewSegment =
      lineSegments.length === 0 ||
      OUTLINE_BULLET_PATTERN.test(line) ||
      /^第.{1,6}(?:步|幕|场|段|节点)/.test(line) ||
      /^(?:开场|铺垫|推进|反转|高潮|收束|结尾)/.test(line);

    if (shouldOpenNewSegment) {
      lineSegments.push(cleanedLine);
      return;
    }

    lineSegments[lineSegments.length - 1] = `${lineSegments[lineSegments.length - 1]} ${cleanedLine}`.trim();
  });

  if (lineSegments.length >= 2) {
    return chunkSegments(lineSegments);
  }

  const sentenceSegments = normalized
    .split(/(?<=[。！？；])/)
    .map((item) => item.replace(/\n/g, " ").trim())
    .filter(Boolean);

  if (sentenceSegments.length >= 2) {
    return chunkSegments(sentenceSegments);
  }

  const clauseSegments = normalized
    .split(/[，、]/)
    .map((item) => item.replace(/\n/g, " ").trim())
    .filter((item) => item.length >= 4);

  if (clauseSegments.length >= 3) {
    return chunkSegments(clauseSegments);
  }

  return [normalized];
}

export function buildOutlineNodes(
  outlineTitle: string | null,
  outlineContent: string | null,
): OutlineNode[] {
  const segments = splitOutlineSegments(outlineContent ?? "");
  const sourceSegments =
    segments.length > 0
      ? segments
      : outlineTitle?.trim()
        ? [outlineTitle.trim()]
        : [];

  return sourceSegments.slice(0, 5).map((segment, index) => {
    const normalized = segment.replace(/\s+/g, " ").trim();
    const titleParts = normalized.split(/[:：]/);
    const explicitTitle =
      titleParts.length > 1 && titleParts[0].trim().length <= 16 ? titleParts[0].trim() : null;
    const fallbackTitleMatch = normalized.match(/^(.{1,16}?)(?:，|。|；|：|、)/);
    const title =
      explicitTitle ??
      fallbackTitleMatch?.[1]?.trim() ??
      normalized.slice(0, Math.min(16, normalized.length)).trim() ??
      `节点 ${index + 1}`;

    return {
      key: `outline-node-${index}-${hashText(normalized)}`,
      index,
      title,
      summary: normalized,
    };
  });
}
