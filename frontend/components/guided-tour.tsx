"use client";

import Link from "next/link";
import { useState } from "react";

interface GuideStep {
  title: string;
  description: string;
  icon: React.ReactNode;
  href?: string;
  action?: {
    label: string;
    href: string;
  };
}

const GUIDED_STEPS: GuideStep[] = [
  {
    title: "1. 分析你的写作风格",
    description: "上传你写过的文字或截图，AI会分析你的文风特征（简洁/华丽、快/慢节奏等）",
    href: "/dashboard/style-analysis",
    icon: (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    title: "2. 设置写作偏好",
    description: "将AI分析的结果应用到你的个人写作偏好，或者手动调整文风、叙事视角、节奏等设置",
    href: "/dashboard/preferences",
    icon: (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
      </svg>
    ),
  },
  {
    title: "3. 选择写作模板",
    description: "在提示词模板库中找到适合你当前场景的模板（打斗、情感、升级、伏笔等），一键应用到章节写作",
    href: "/dashboard/prompt-templates",
    icon: (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
      </svg>
    ),
  },
  {
    title: "4. 开始写作",
    description: "在故事工作台中，按照大纲和模板开始正文写作。系统会记住你的风格偏好，保持文风一致",
    icon: (
      <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
      </svg>
    ),
  },
];

interface FeatureCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  href?: string;
  badge?: string;
}

function FeatureCard({ title, description, icon, href, badge }: FeatureCardProps) {
  const content = (
    <div className="flex items-start gap-4 rounded-[20px] border border-black/10 bg-[#fbfaf5] p-4 transition hover:border-copper/40 hover:bg-[#f6f0e6]/30">
      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-black/10 bg-white">
        <span className="text-copper">{icon}</span>
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-black/84">{title}</h3>
          {badge && (
            <span className="rounded-full border border-copper/20 bg-[#f6ede3] px-2 py-0.5 text-xs text-copper">
              {badge}
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-black/55">{description}</p>
      </div>
      {href && (
        <span className="flex h-6 w-6 items-center justify-center text-black/30">
          →
        </span>
      )}
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="block">
        {content}
      </Link>
    );
  }

  return content;
}

interface PlatformGuideProps {
  hasProjects?: boolean;
}

export function PlatformGuide({ hasProjects = false }: PlatformGuideProps) {
  const [expanded, setExpanded] = useState(!hasProjects);

  return (
    <section className="rounded-[32px] border border-copper/20 bg-copper/[0.03] p-6">
      <button
        type="button"
        className="flex w-full items-center justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <span className="text-2xl">💡</span>
          <div className="text-left">
            <h2 className="text-lg font-semibold">新手引导 · 写作工作流</h2>
            <p className="text-sm text-black/55">
              {expanded ? "点击收起" : "点击展开，了解如何高效使用这个平台"}
            </p>
          </div>
        </div>
        <span
          className={`text-lg text-black/40 transition-transform ${expanded ? "rotate-180" : ""}`}
        >
          ▼
        </span>
      </button>

      {expanded && (
        <div className="mt-6 grid gap-4">
          <div className="rounded-[24px] border border-amber-200/50 bg-amber-50/50 p-4">
            <p className="text-sm text-amber-800">
              <strong>核心理念：</strong>这个平台通过「风格分析 → 偏好设置 → 模板写作」的工作流，
              帮助你保持一致的文风，让AI更懂你的写作风格。
            </p>
          </div>

          <div className="grid gap-3">
            {GUIDED_STEPS.map((step, index) => (
              <FeatureCard
                key={step.title}
                title={step.title}
                description={step.description}
                icon={step.icon}
                href={step.href}
                badge={index === 0 ? "推荐先做" : index === 3 ? "进行中" : undefined}
              />
            ))}
          </div>

          <div className="mt-4 rounded-[20px] border border-black/10 bg-white p-4">
            <h3 className="font-semibold text-black/84 mb-2">什么是「风格」？</h3>
            <div className="space-y-2 text-sm text-black/62">
              <p>
                <strong className="text-copper">写作偏好</strong> = 你的长期写作习惯，
                比如喜欢用短句还是长句、节奏快还是慢、对话多还是少。
                这些设置会被记住，下次写作时自动应用。
              </p>
              <p>
                <strong className="text-copper">提示词模板</strong> = 具体场景的写作框架，
                比如「英雄救美」场景应该怎么写开头、怎么制造冲突、怎么收尾。
                模板不会改变你的文风，只提供场景结构。
              </p>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}