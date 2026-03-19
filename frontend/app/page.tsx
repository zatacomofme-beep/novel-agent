import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen px-6 py-12 text-ink">
      <div className="mx-auto flex max-w-5xl flex-col gap-8">
        <section className="rounded-3xl border border-black/10 bg-white/70 p-10 shadow-[0_20px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <p className="mb-3 text-sm uppercase tracking-[0.25em] text-copper">
            Long Novel Agent
          </p>
          <h1 className="max-w-3xl text-5xl font-semibold leading-tight">
            为长篇小说创作搭建的多 Agent 工作台，当前处于基础工程搭建阶段。
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-black/70">
            当前已进入全量执行模式。下一步将落地数据模型、鉴权、Story Bible、
            章节生成链路与质量评估体系。
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              className="rounded-2xl bg-ink px-4 py-3 text-sm font-medium text-paper"
              href="/login"
            >
              登录
            </Link>
            <Link
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium"
              href="/register"
            >
              注册
            </Link>
            <Link
              className="rounded-2xl border border-black/10 bg-white px-4 py-3 text-sm font-medium"
              href="/dashboard"
            >
              项目仪表板
            </Link>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-black/10 bg-white/60 p-6">
            <h2 className="text-xl font-semibold">Phase 0 / 1</h2>
            <p className="mt-3 text-sm leading-7 text-black/70">
              执行版 PRD、前后端骨架、Docker、本地开发基础设施。
            </p>
          </div>
          <div className="rounded-2xl border border-black/10 bg-white/60 p-6">
            <h2 className="text-xl font-semibold">Next Batch</h2>
            <p className="mt-3 text-sm leading-7 text-black/70">
              数据模型、Alembic 迁移、认证、项目与 Story Bible API。
            </p>
          </div>
          <div className="rounded-2xl border border-black/10 bg-white/60 p-6">
            <h2 className="text-xl font-semibold">Target</h2>
            <p className="mt-3 text-sm leading-7 text-black/70">
              打通长篇创作闭环：设定、生成、评估、反思、版本与导出。
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
