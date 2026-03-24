import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-screen px-6 py-12 text-ink">
      <div className="mx-auto flex max-w-5xl flex-col gap-8">
        <section className="rounded-3xl border border-black/10 bg-white/70 p-10 shadow-[0_20px_60px_rgba(16,20,23,0.08)] backdrop-blur">
          <p className="mb-3 text-sm uppercase tracking-[0.25em] text-copper">
            网文创作平台
          </p>
          <h1 className="max-w-3xl text-5xl font-semibold leading-tight">
            一套工作台，写完大纲、正文、设定和终稿。
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-black/70">
            这里不需要你理解后台怎么跑。你只管写脑洞、出正文、看优化稿和自动沉淀下来的设定圣经，
            后台会把长篇创作里最容易崩的人设、剧情、伏笔和连续性收住。
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
              进入项目页
            </Link>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-4">
          <div className="rounded-2xl border border-black/10 bg-white/60 p-6">
            <h2 className="text-xl font-semibold">测大纲漏洞</h2>
            <p className="mt-3 text-sm leading-7 text-black/70">
              把模糊脑洞压成三级大纲，先把大坑和长线矛盾揪出来。
            </p>
          </div>
          <div className="rounded-2xl border border-black/10 bg-white/60 p-6">
            <h2 className="text-xl font-semibold">开始写正文</h2>
            <p className="mt-3 text-sm leading-7 text-black/70">
              流式起稿、继续往下写、查人设 bug，全都在同一页完成。
            </p>
          </div>
          <div className="rounded-2xl border border-black/10 bg-white/60 p-6">
            <h2 className="text-xl font-semibold">自动记设定</h2>
            <p className="mt-3 text-sm leading-7 text-black/70">
              人物、伏笔、物品、地点、势力、剧情线会自动收进设定圣经。
            </p>
          </div>
          <div className="rounded-2xl border border-black/10 bg-white/60 p-6">
            <h2 className="text-xl font-semibold">一键收终稿</h2>
            <p className="mt-3 text-sm leading-7 text-black/70">
              直接看原稿和优化稿对比，再拿到本章 100-300 字总结和设定更新清单。
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
