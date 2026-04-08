"use client";

import { useState } from "react";

interface HeaderInfoProps {
  projectTitle: string;
  genre?: string | null;
  tone?: string | null;
  knowledgeItemCount: number;
  chapterNumber: number;
}

export function HeaderInfo({
  projectTitle,
  genre,
  tone,
  knowledgeItemCount,
  chapterNumber,
}: HeaderInfoProps) {
  const [showDetails, setShowDetails] = useState(false);

  return (
    <div>
      <h1 className="text-2xl font-semibold">{projectTitle}</h1>
      <button
        onClick={() => setShowDetails(!showDetails)}
        className="mt-2 text-xs text-black/45 hover:text-black/70"
        type="button"
      >
        {showDetails ? "收起详情 ∧" : "展开详情 ∨"}
      </button>
      {showDetails && (
        <div className="mt-3 flex flex-wrap gap-2">
          {genre && (
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              题材：{genre}
            </span>
          )}
          {tone && (
            <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
              气质：{tone}
            </span>
          )}
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
            设定条目：{knowledgeItemCount}
          </span>
          <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
            当前章节：第 {chapterNumber} 章
          </span>
        </div>
      )}
    </div>
  );
}
