"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiFetchWithAuth } from "@/lib/api";
import { loadAuthSession, getAccessToken } from "@/lib/auth";

interface PromptTemplate {
  id: string;
  name: string;
  tagline: string;
  description: string;
  category: string;
  tags: string[];
  content: string;
  variables: { name: string; description: string; required: boolean }[];
  use_count: number;
  is_system: boolean;
  recommended_scenes: string[];
  difficulty_level: string;
}

interface ListResponse {
  templates: PromptTemplate[];
  total: number;
  categories: string[];
}

const DIFFICULTY_LABELS: Record<string, string> = {
  beginner: "入门",
  intermediate: "进阶",
  advanced: "高级",
};

const DIFFICULTY_COLORS: Record<string, string> = {
  beginner: "bg-green-100 text-green-700",
  intermediate: "bg-yellow-100 text-yellow-700",
  advanced: "bg-red-100 text-red-700",
};

function TemplateCard({
  template,
  onView,
}: {
  template: PromptTemplate;
  onView: (t: PromptTemplate) => void;
}) {
  return (
    <div className="rounded-[24px] border border-black/10 bg-white/75 p-5 shadow-[0_12px_32px_rgba(16,20,23,0.06)] hover:shadow-[0_18px_40px_rgba(16,20,23,0.1)] transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="font-semibold text-black/84 mb-1">{template.name}</h3>
          <p className="text-sm text-copper">{template.tagline}</p>
        </div>
        <span
          className={`ml-2 px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${
            DIFFICULTY_COLORS[template.difficulty_level] ||
            "bg-[#fbfaf5] text-black/40"
          }`}
        >
          {DIFFICULTY_LABELS[template.difficulty_level] || template.difficulty_level}
        </span>
      </div>
      <p className="text-sm text-black/55 line-clamp-2 mb-3">{template.description}</p>
      <div className="flex flex-wrap gap-1 mb-3">
        <span className="px-2 py-0.5 bg-[#fbfaf5] text-black/40 text-xs rounded-full">
          {template.category}
        </span>
        {template.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="px-2 py-0.5 bg-[#f8efe3] text-copper/80 text-xs rounded-full"
          >
            {tag}
          </span>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <span className="text-xs text-black/30">
          使用 {template.use_count} 次
        </span>
        <button
          onClick={() => onView(template)}
          className="text-sm text-copper hover:text-copper/70 font-medium"
        >
          查看详情 →
        </button>
      </div>
    </div>
  );
}

function TemplateModal({
  template,
  onClose,
}: {
  template: PromptTemplate;
  onClose: () => void;
}) {
  const [activeTab, setActiveTab] = useState<"content" | "variables" | "examples">("content");
  const [copied, setCopied] = useState(false);
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(template.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleApplyToChapter = async () => {
    setApplying(true);
    try {
      const token = getAccessToken();
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/prompt-templates/${template.id}/apply`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            project_id: window.location.pathname.split("/")[3],
            variables: {},
          }),
        }
      );
      
      if (!res.ok) throw new Error();
      
      const result = await res.json();
      
      // 跳转到 story-room 并传递模板内容
      const params = new URLSearchParams({
        template_content: encodeURIComponent(result.content),
        template_name: encodeURIComponent(template.name),
      });
      window.location.href = `/dashboard/projects/${window.location.pathname.split("/")[3]}/story-room?${params.toString()}`;
      
      setApplied(true);
      setTimeout(() => {
        onClose();
      }, 1000);
    } catch (err) {
      console.error("Failed to apply template:", err);
      alert("应用模板失败，请重试");
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="rounded-[32px] border border-black/10 bg-white/95 max-w-2xl w-full max-h-[85vh] flex flex-col shadow-[0_24px_80px_rgba(16,20,23,0.18)]">
        <div className="p-6 border-b border-black/10">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-semibold text-black/84 mb-1">{template.name}</h2>
              <p className="text-copper">{template.tagline}</p>
            </div>
            <button
              onClick={onClose}
              className="text-black/30 hover:text-black/60 text-3xl leading-none"
            >
              ×
            </button>
          </div>
          <div className="flex gap-2 mt-3 flex-wrap">
            <span
              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                DIFFICULTY_COLORS[template.difficulty_level] ||
                "bg-[#fbfaf5] text-black/40"
              }`}
            >
              {DIFFICULTY_LABELS[template.difficulty_level]}
            </span>
            <span className="px-2 py-0.5 bg-[#fbfaf5] text-black/40 text-xs rounded-full">
              {template.category}
            </span>
            {template.recommended_scenes.map((scene) => (
              <span
                key={scene}
                className="px-2 py-0.5 bg-[#f8efe3] text-copper/80 text-xs rounded-full"
              >
                {scene}
              </span>
            ))}
          </div>
        </div>

        <div className="flex border-b border-black/10">
          <button
            onClick={() => setActiveTab("content")}
            className={`px-6 py-3 text-sm font-medium ${
              activeTab === "content"
                ? "text-copper border-b-2 border-copper"
                : "text-black/40 hover:text-black/60"
            }`}
          >
            模板内容
          </button>
          <button
            onClick={() => setActiveTab("variables")}
            className={`px-6 py-3 text-sm font-medium ${
              activeTab === "variables"
                ? "text-copper border-b-2 border-copper"
                : "text-black/40 hover:text-black/60"
            }`}
          >
            变量说明 ({template.variables.length})
          </button>
          <button
            onClick={() => setActiveTab("examples")}
            className={`px-6 py-3 text-sm font-medium ${
              activeTab === "examples"
                ? "text-copper border-b-2 border-copper"
                : "text-black/40 hover:text-black/60"
            }`}
          >
            使用示例
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {activeTab === "content" ? (
            <div>
              <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-4 mb-4">
                <p className="text-xs text-black/40 mb-2 uppercase tracking-wider">适用场景</p>
                <div className="flex flex-wrap gap-1">
                  {template.recommended_scenes.map((scene) => (
                    <span
                      key={scene}
                      className="px-2 py-0.5 bg-white border border-black/10 text-black/55 text-xs rounded-full"
                    >
                      {scene}
                    </span>
                  ))}
                </div>
              </div>
              <pre className="whitespace-pre-wrap text-sm text-black/72 font-sans leading-relaxed bg-[#fbfaf5] p-4 rounded-[18px] border border-black/10 max-h-80 overflow-y-auto">
                {template.content}
              </pre>
            </div>
          ) : activeTab === "variables" ? (
            <div className="space-y-3">
              {template.variables.length === 0 ? (
                <p className="text-sm text-black/40">此模板无需变量</p>
              ) : (
                template.variables.map((v, i) => (
                  <div
                    key={i}
                    className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-4"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-black/84">{v.name}</span>
                      {v.required ? (
                        <span className="px-1.5 py-0.5 bg-[#f8efe3] text-copper/80 text-xs rounded-full">
                          必填
                        </span>
                      ) : (
                        <span className="px-1.5 py-0.5 bg-white text-black/40 text-xs rounded-full">
                          选填
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-black/55">{v.description}</p>
                  </div>
                ))
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="rounded-[18px] border border-amber-200 bg-amber-50 p-4">
                <p className="text-sm text-amber-800">
                  💡 <strong>使用提示：</strong>点击"应用到当前章节"后，系统会自动打开写作界面并填充模板内容。
                  您可以根据需要修改占位符（如 [角色名]、[地点] 等），然后开始写作。
                </p>
              </div>
              <div className="rounded-[18px] border border-black/10 bg-[#fbfaf5] p-4">
                <p className="text-xs text-black/40 mb-2 uppercase tracking-wider">示例用法</p>
                <p className="text-sm text-black/60 leading-relaxed">
                  假设这是一个"打斗场景"模板，使用时：
                </p>
                <ol className="mt-2 text-sm text-black/60 leading-relaxed list-decimal list-inside space-y-1">
                  <li>点击"应用到当前章节"</li>
                  <li>系统会自动打开写作界面</li>
                  <li>将占位符替换为实际内容（如将"[角色名]"替换为"萧炎"）</li>
                  <li>根据需要调整和完善内容</li>
                </ol>
              </div>
            </div>
          )}
        </div>

        <div className="p-6 border-t border-black/10 flex gap-3">
          <button
            onClick={handleCopy}
            className="flex-1 rounded-[22px] border border-black/10 bg-white py-2.5 text-sm font-medium text-black/62 hover:bg-[#f6f0e6] transition-colors"
          >
            {copied ? "已复制 ✓" : "复制模板内容"}
          </button>
          <button
            onClick={handleApplyToChapter}
            disabled={applying}
            className={`flex-1 rounded-[22px] py-2.5 text-sm font-medium transition-colors ${
              applied
                ? "bg-green-600 text-white"
                : "bg-ink text-paper hover:bg-copper"
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {applying ? "应用中..." : applied ? "已应用 ✓" : "应用到当前章节"}
          </button>
          <button
            onClick={onClose}
            className="flex-1 rounded-[22px] bg-white border border-black/10 py-2.5 text-sm font-medium text-black/62 hover:bg-[#f6f0e6] transition-colors"
          >
            关闭
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateTemplateModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [formData, setFormData] = useState({
    name: "",
    tagline: "",
    description: "",
    category: "世界观构建",
    tags: "",
    content: "",
    difficulty_level: "intermediate",
    recommended_scenes: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const token = getAccessToken();
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/prompt-templates`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...formData,
          tags: formData.tags.split(",").map((t) => t.trim()).filter(Boolean),
          recommended_scenes: formData.recommended_scenes.split(",").map((s) => s.trim()).filter(Boolean),
          variables: [],
        }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || "创建失败");
      }

      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="rounded-[32px] border border-black/10 bg-white/95 max-w-2xl w-full max-h-[90vh] flex flex-col shadow-[0_24px_80px_rgba(16,20,23,0.18)]">
        <div className="p-6 border-b border-black/10">
          <h2 className="text-2xl font-semibold text-black/84">创建自定义模板</h2>
          <p className="text-sm text-black/55 mt-1">创建属于您自己的写作模板</p>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-6 space-y-4">
          {error && (
            <div className="rounded-[18px] border border-red-200 bg-red-50 p-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-black/84 mb-1">模板名称 *</label>
            <input
              type="text"
              required
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              className="w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none focus:border-copper"
              placeholder="如：玄幻升级递进模板"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-black/84 mb-1">一句话简介 *</label>
            <input
              type="text"
              required
              value={formData.tagline}
              onChange={(e) => setFormData({ ...formData, tagline: e.target.value })}
              className="w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none focus:border-copper"
              placeholder="如：经典的修仙/玄幻实力提升路径"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-black/84 mb-1">详细描述 *</label>
            <textarea
              required
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none focus:border-copper min-h-[80px]"
              placeholder="描述模板的用途和适用场景..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-black/84 mb-1">分类 *</label>
              <select
                required
                value={formData.category}
                onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                className="w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none focus:border-copper"
              >
                {[
                  "世界观构建",
                  "角色塑造",
                  "情节设计",
                  "打斗战斗",
                  "情感描写",
                  "升级进化",
                  "伏笔悬念",
                  "章尾钩子",
                  "起承转合",
                  "场景转换",
                  "高潮设计",
                  "结局收束",
                ].map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-black/84 mb-1">难度 *</label>
              <select
                required
                value={formData.difficulty_level}
                onChange={(e) => setFormData({ ...formData, difficulty_level: e.target.value })}
                className="w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none focus:border-copper"
              >
                <option value="beginner">入门</option>
                <option value="intermediate">进阶</option>
                <option value="advanced">高级</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-black/84 mb-1">标签</label>
            <input
              type="text"
              value={formData.tags}
              onChange={(e) => setFormData({ ...formData, tags: e.target.value })}
              className="w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none focus:border-copper"
              placeholder="用逗号分隔，如：玄幻，仙侠，升级"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-black/84 mb-1">推荐场景</label>
            <input
              type="text"
              value={formData.recommended_scenes}
              onChange={(e) => setFormData({ ...formData, recommended_scenes: e.target.value })}
              className="w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none focus:border-copper"
              placeholder="用逗号分隔，如：新章开局，突破节点"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-black/84 mb-1">模板内容 *</label>
            <textarea
              required
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              className="w-full rounded-[18px] border border-black/10 bg-[#fbfaf5] px-4 py-3 text-sm outline-none focus:border-copper min-h-[200px]"
              placeholder="输入模板的具体内容，可以使用 Markdown 格式..."
            />
          </div>
        </form>

        <div className="p-6 border-t border-black/10 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-[22px] border border-black/10 bg-white py-2.5 text-sm font-medium text-black/62 hover:bg-[#f6f0e6] transition-colors"
          >
            取消
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={loading}
            className="flex-1 rounded-[22px] bg-ink text-paper py-2.5 text-sm font-medium hover:bg-copper transition-colors disabled:opacity-50"
          >
            {loading ? "创建中..." : "创建模板"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PromptTemplatesPage() {
  const router = useRouter();
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("");
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>("");
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null);
  const [page, setPage] = useState(1);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const pageSize = 20;

  const loadTemplates = useCallback(
    async (resetPage = false) => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (search) params.set("search", search);
        if (selectedCategory) params.set("category", selectedCategory);
        if (selectedDifficulty) params.set("difficulty", selectedDifficulty);
        params.set("page", String(resetPage ? 1 : page));
        params.set("page_size", String(pageSize));

        const data = await apiFetchWithAuth<ListResponse>(
          `/api/v1/prompt-templates?${params.toString()}`
        );
        setTemplates(data.templates);
        setCategories(data.categories);
        setTotal(data.total);
        if (resetPage) setPage(1);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    },
    [search, selectedCategory, selectedDifficulty, page]
  );

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadTemplates(true);
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="max-w-6xl mx-auto py-8 px-4">
      <div className="rounded-[36px] border border-black/10 bg-white/75 p-8 shadow-[0_18px_60px_rgba(16,20,23,0.08)] mb-6">
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => router.push("/dashboard")}
            className="p-2 rounded-full hover:bg-black/5 transition-colors"
            title="返回工作台"
          >
            <svg className="w-5 h-5 text-black/55" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm text-black/40">返回工作台</span>
        </div>
        <p className="text-sm uppercase tracking-[0.24em] text-copper">写作工具</p>
        <h1 className="mt-3 text-4xl font-semibold">提示词模板库</h1>
        <p className="mt-4 max-w-xl text-sm leading-7 text-black/62">
          预置海量写作场景模板，涵盖打斗、情感、升级、伏笔、章尾钩子等各类写作技巧。搜索、分类、复制，轻松使用。
        </p>
        <div className="mt-4 flex gap-3">
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-6 py-2.5 bg-ink text-paper rounded-[22px] text-sm font-medium hover:bg-copper transition-colors"
          >
            + 创建自定义模板
          </button>
          <a
            href="/dashboard/preferences"
            className="px-6 py-2.5 bg-[#fbfaf5] border border-black/10 text-black/62 rounded-[22px] text-sm font-medium hover:bg-[#f6f0e6] transition-colors"
          >
            风格中心 →
          </a>
        </div>
      </div>

      <form onSubmit={handleSearch} className="mb-6 flex gap-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="搜索模板名称、描述..."
          className="flex-1 rounded-[22px] border border-black/10 bg-white/75 px-4 py-3 text-sm text-black/72 outline-none transition focus:border-copper"
        />
        <button
          type="submit"
          className="px-6 py-2.5 bg-ink text-paper rounded-[22px] text-sm font-medium hover:bg-copper transition-colors"
        >
          搜索
        </button>
      </form>

      <div className="flex gap-2 flex-wrap mb-6">
        <button
          onClick={() => {
            setSelectedCategory("");
            setPage(1);
          }}
          className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
            !selectedCategory
              ? "bg-copper text-paper"
              : "bg-[#fbfaf5] text-black/55 hover:bg-[#f6f0e6]"
          }`}
        >
          全部
        </button>
        {categories.map((cat) => (
          <button
            key={cat}
            onClick={() => {
              setSelectedCategory(cat);
              setPage(1);
            }}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              selectedCategory === cat
                ? "bg-copper text-paper"
                : "bg-[#fbfaf5] text-black/55 hover:bg-[#f6f0e6]"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="flex gap-2 mb-6">
        <span className="text-sm text-black/40 py-1.5">难度：</span>
        {["", "beginner", "intermediate", "advanced"].map((d) => (
          <button
            key={d}
            onClick={() => {
              setSelectedDifficulty(d);
              setPage(1);
            }}
            className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
              selectedDifficulty === d
                ? "bg-copper text-paper"
                : "bg-[#fbfaf5] text-black/55 hover:bg-[#f6f0e6]"
            }`}
          >
            {d === "" ? "全部" : DIFFICULTY_LABELS[d]}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-20 text-sm text-black/40">加载中...</div>
      ) : templates.length === 0 ? (
        <div className="text-center py-20 text-sm text-black/40">
          未找到匹配的模板，试试其他关键词或分类
        </div>
      ) : (
        <>
          <div className="mb-4 text-sm text-gray-500">
            共 {total} 个模板
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                template={t}
                onView={setSelectedTemplate}
              />
            ))}
          </div>

          {totalPages > 1 && (
            <div className="flex justify-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-4 py-2 bg-[#fbfaf5] text-black/55 rounded-[18px] disabled:opacity-50 hover:bg-[#f6f0e6] transition-colors text-sm"
              >
                上一页
              </button>
              <span className="px-4 py-2 text-sm text-black/40">
                第 {page} / {totalPages} 页
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="px-4 py-2 bg-[#fbfaf5] text-black/55 rounded-[18px] disabled:opacity-50 hover:bg-[#f6f0e6] transition-colors text-sm"
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}

      {selectedTemplate && (
        <TemplateModal
          template={selectedTemplate}
          onClose={() => setSelectedTemplate(null)}
        />
      )}

      {showCreateModal && (
        <CreateTemplateModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => loadTemplates(true)}
        />
      )}
    </div>
  );
}
