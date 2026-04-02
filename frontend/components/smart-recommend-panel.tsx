"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface RecommendedTemplate {
  id: string;
  name: string;
  category: string;
  tags: string[];
  description: string;
  use_count: number;
}

interface SmartRecommendPanelProps {
  projectId?: string;
  chapterId?: string;
  chapterContent?: string;
  context?: string;
  onSelectTemplate?: (template: RecommendedTemplate) => void;
  compact?: boolean;
}

export function SmartRecommendPanel({
  projectId,
  chapterId,
  chapterContent,
  context,
  onSelectTemplate,
  compact = false,
}: SmartRecommendPanelProps) {
  const [templates, setTemplates] = useState<RecommendedTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(!compact);

  useEffect(() => {
    async function fetchRecommendations() {
      if (!projectId) return;

      setLoading(true);
      try {
        const response = await fetch(`/api/v1/prompt-templates/recommend`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("auth_token") || ""}`,
          },
          body: JSON.stringify({
            project_id: projectId,
            chapter_id: chapterId,
            chapter_content: chapterContent,
            context: context,
          }),
        });

        if (response.ok) {
          const data = await response.json();
          setTemplates(data.templates || []);
        }
      } catch (error) {
        console.error("Failed to fetch recommendations:", error);
      } finally {
        setLoading(false);
      }
    }

    const debounce = setTimeout(fetchRecommendations, 800);
    return () => clearTimeout(debounce);
  }, [projectId, chapterId, chapterContent, context]);

  if (templates.length === 0 && !loading) {
    return null;
  }

  const categoryLabels: Record<string, string> = {
    "世界观构建": "🌍",
    "角色塑造": "👤",
    "情节设计": "📖",
    "打斗战斗": "⚔️",
    "情感描写": "💕",
    "升级进化": "📈",
    "伏笔悬念": "🔮",
    "章尾钩子": "🎣",
    "起承转合": "📊",
    "场景转换": "🎬",
    "高潮设计": "🔥",
    "结局收束": "🎬",
  };

  if (compact) {
    return (
      <div className="rounded-2xl border border-copper/20 bg-copper/[0.03] p-4">
        <button
          type="button"
          className="flex w-full items-center justify-between"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-2">
            <span className="text-lg">✨</span>
            <span className="font-medium text-copper">智能推荐模板</span>
            <span className="text-xs text-black/40">({templates.length})</span>
          </div>
          <span className={`text-xs text-black/40 transition-transform ${expanded ? "rotate-180" : ""}`}>
            ▼
          </span>
        </button>

        {expanded && (
          <div className="mt-3 grid gap-2">
            {templates.slice(0, 3).map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => onSelectTemplate?.(template)}
                className="flex items-center gap-3 rounded-xl border border-black/10 bg-white p-3 text-left transition hover:border-copper/40 hover:bg-[#f6f0e6]/30"
              >
                <span className="text-lg">{categoryLabels[template.category] || "📝"}</span>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm truncate">{template.name}</p>
                  <p className="text-xs text-black/50 truncate">{template.description}</p>
                </div>
              </button>
            ))}
            <Link
              href="/dashboard/prompt-templates"
              className="flex items-center justify-center gap-1 rounded-xl border border-dashed border-black/20 p-2 text-xs text-black/50 hover:border-copper/40 hover:text-copper"
            >
              查看全部模板 →
            </Link>
          </div>
        )}
      </div>
    );
  }

  return (
    <section className="rounded-[28px] border border-copper/20 bg-copper/[0.03] p-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-2xl">✨</span>
          <div>
            <h3 className="font-semibold">智能推荐模板</h3>
            <p className="text-sm text-black/55">
              根据当前写作场景自动推荐 {templates.length} 个合适模板
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="rounded-full border border-black/10 bg-white px-3 py-1 text-xs text-black/55 hover:bg-[#f6f0e6]"
        >
          {expanded ? "收起" : "展开"}
        </button>
      </div>

      {expanded && (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {templates.map((template) => (
            <button
              key={template.id}
              type="button"
              onClick={() => onSelectTemplate?.(template)}
              className="flex items-start gap-3 rounded-2xl border border-black/10 bg-white p-4 text-left transition hover:border-copper/40 hover:shadow-md"
            >
              <span className="text-2xl">{categoryLabels[template.category] || "📝"}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className="font-semibold truncate">{template.name}</h4>
                </div>
                <p className="mt-1 text-xs text-black/55 line-clamp-2">{template.description}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {template.tags.slice(0, 3).map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-black/10 bg-[#fbfaf5] px-2 py-0.5 text-xs text-black/50"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <p className="mt-2 text-xs text-copper">
                  使用 {template.use_count} 次
                </p>
              </div>
            </button>
          ))}
        </div>
      )}

      {expanded && (
        <div className="mt-4 flex items-center justify-center">
          <Link
            href="/dashboard/prompt-templates"
            className="rounded-full border border-dashed border-copper/40 px-4 py-2 text-sm text-copper hover:bg-copper/10"
          >
            浏览全部 {templates.length}+ 模板 →
          </Link>
        </div>
      )}
    </section>
  );
}