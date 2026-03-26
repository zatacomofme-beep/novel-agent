import Link from "next/link";

const NEW_BOOK_REDIRECT = encodeURIComponent("/dashboard?intent=new");

const problemCards = [
  {
    title: "人设不崩",
    detail: "角色、关系、伏笔持续守住。",
  },
  {
    title: "剧情不断",
    detail: "大纲到正文始终在一条线上。",
  },
  {
    title: "上下文不丢",
    detail: "每章自动回写设定与总结。",
  },
];

const methodCards = [
  {
    title: "三级大纲锁主线",
    detail: "先立书，再拆卷，再写章。",
  },
  {
    title: "多轮模型辩论",
    detail: "发现冲突，立即收口。",
  },
  {
    title: "设定圣经自动更新",
    detail: "越写越稳，越写越顺。",
  },
];

const statusCards = [
  {
    label: "大纲状态",
    value: "已锁定",
    note: "主线 / 分卷 / 章纲",
  },
  {
    label: "正文状态",
    value: "生成中",
    note: "按章推进，不跳线",
  },
  {
    label: "设定状态",
    value: "已沉淀",
    note: "人物 / 物品 / 伏笔",
  },
];

const signalTags = [
  "百万字长篇小说再也不崩盘",
  "更易用的 AI 写手软件",
  "长篇一致性优先",
  "自动记设定",
];

export default function HomePage() {
  return (
    <main className="min-h-screen px-6 py-6 text-ink md:px-8 md:py-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-6">
        <header className="rounded-[30px] border border-black/10 bg-white/72 px-6 py-4 shadow-[0_18px_50px_rgba(16,20,23,0.06)] backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-ink text-sm font-semibold tracking-[0.18em] text-paper">
                NA
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-copper">Novel Agent</p>
                <p className="mt-1 text-sm text-black/56">AI 网文创作平台</p>
              </div>
            </div>

            <nav className="flex flex-wrap items-center gap-3">
              <Link
                className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                href="/login"
              >
                登录
              </Link>
              <Link
                className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-paper transition hover:bg-copper"
                href={`/register?redirect=${NEW_BOOK_REDIRECT}`}
              >
                创建新书
              </Link>
            </nav>
          </div>
        </header>

        <section className="grid gap-6 xl:grid-cols-[1.04fr_0.96fr]">
          <article className="relative overflow-hidden rounded-[44px] border border-black/10 bg-white/82 p-8 shadow-[0_26px_70px_rgba(16,20,23,0.08)] backdrop-blur md:p-10 xl:p-12">
            <div className="absolute -right-10 top-0 h-60 w-60 rounded-full bg-[rgba(139,74,43,0.13)] blur-3xl" />
            <div className="absolute bottom-0 left-0 h-48 w-48 rounded-full bg-[rgba(86,98,70,0.1)] blur-3xl" />

            <div className="relative max-w-4xl">
              <p className="text-sm uppercase tracking-[0.24em] text-copper">更易用的 AI 写手软件</p>
              <h1 className="mt-4 text-5xl font-semibold leading-[0.98] md:text-7xl xl:text-[5.4rem]">
                百万字长篇小说，
                <br />
                再也不崩盘。
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-black/64">
                用三级大纲、设定圣经和多轮模型辩论，把长篇从灵感一路推到终稿。
              </p>
            </div>

            <div className="relative mt-8 flex flex-wrap gap-3">
              <Link
                className="rounded-full bg-ink px-6 py-3 text-sm font-semibold text-paper transition hover:bg-copper"
                href={`/register?redirect=${NEW_BOOK_REDIRECT}`}
              >
                创建新书
              </Link>
              <Link
                className="rounded-full border border-black/10 bg-white px-6 py-3 text-sm font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                href="/login"
              >
                登录继续写
              </Link>
            </div>

            <div className="relative mt-8 flex flex-wrap gap-2">
              {signalTags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-2 text-xs font-medium text-black/62"
                >
                  {tag}
                </span>
              ))}
            </div>
          </article>

          <aside className="relative overflow-hidden rounded-[44px] border border-black/10 bg-[#1f2629] p-6 text-paper shadow-[0_26px_70px_rgba(16,20,23,0.14)] md:p-8">
            <div className="absolute right-0 top-0 h-40 w-40 rounded-full bg-[rgba(245,239,227,0.1)] blur-3xl" />
            <div className="absolute bottom-0 left-0 h-44 w-44 rounded-full bg-[rgba(139,74,43,0.16)] blur-3xl" />

            <div className="relative flex h-full flex-col gap-5">
              <div className="rounded-[28px] border border-white/10 bg-white/8 p-5">
                <p className="text-xs uppercase tracking-[0.18em] text-[rgba(245,239,227,0.56)]">我们是做什么的</p>
                <h2 className="mt-3 text-3xl font-semibold leading-tight md:text-4xl">
                  给网文写手的
                  <br />
                  长篇创作平台。
                </h2>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
                {statusCards.map((item) => (
                  <article
                    key={item.label}
                    className="rounded-[24px] border border-white/10 bg-white/8 px-4 py-4"
                  >
                    <p className="text-xs uppercase tracking-[0.16em] text-[rgba(245,239,227,0.52)]">
                      {item.label}
                    </p>
                    <p className="mt-2 text-2xl font-semibold">{item.value}</p>
                    <p className="mt-2 text-sm text-[rgba(245,239,227,0.7)]">{item.note}</p>
                  </article>
                ))}
              </div>

              <div className="rounded-[30px] border border-[rgba(245,239,227,0.12)] bg-[rgba(245,239,227,0.08)] p-5">
                <p className="text-xs uppercase tracking-[0.18em] text-[rgba(245,239,227,0.56)]">一句话</p>
                <p className="mt-3 text-xl font-semibold leading-8">
                  先把书写稳，
                  <br />
                  再把速度拉起来。
                </p>
              </div>
            </div>
          </aside>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {problemCards.map((item) => (
            <article
              key={item.title}
              className="rounded-[30px] border border-black/10 bg-white/76 p-6 shadow-[0_18px_40px_rgba(16,20,23,0.05)]"
            >
              <p className="text-xs uppercase tracking-[0.18em] text-copper">解决什么问题</p>
              <h2 className="mt-3 text-3xl font-semibold">{item.title}</h2>
              <p className="mt-3 text-sm leading-7 text-black/62">{item.detail}</p>
            </article>
          ))}
        </section>

        <section className="rounded-[40px] border border-black/10 bg-[#fff8f0] p-6 shadow-[0_22px_60px_rgba(16,20,23,0.05)] md:p-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.22em] text-copper">我们怎么做</p>
              <h2 className="mt-2 text-3xl font-semibold">把长篇最容易出问题的地方，一个个锁住。</h2>
            </div>
            <Link
              className="rounded-full border border-black/10 bg-white px-4 py-2 text-sm font-semibold text-black/70 transition hover:bg-[#f6f0e6]"
              href={`/register?redirect=${NEW_BOOK_REDIRECT}`}
            >
              现在开始
            </Link>
          </div>

          <div className="mt-6 grid gap-4 xl:grid-cols-3">
            {methodCards.map((item) => (
              <article
                key={item.title}
                className="rounded-[28px] border border-black/10 bg-white p-6 shadow-[0_12px_30px_rgba(16,20,23,0.04)]"
              >
                <h3 className="text-2xl font-semibold">{item.title}</h3>
                <p className="mt-3 text-sm leading-7 text-black/62">{item.detail}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
