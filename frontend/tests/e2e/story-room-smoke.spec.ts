import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const FRONTEND_BASE_URL =
  process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3000";
const API_BASE_URL =
  process.env.PLAYWRIGHT_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://127.0.0.1:8000";
const API_V1_PREFIX = `${API_BASE_URL}/api/v1/`;

const AUTH_STORAGE_KEY = "long-novel-agent.auth";
const AUTH_COOKIE_KEY = "novel_agent_token";
const DEFAULT_PASSWORD = "StoryRoomE2E123!";

type ApiUser = {
  id: string;
  email: string;
};

type TokenResponse = {
  access_token: string;
  token_type: string;
  user: ApiUser;
};

type ProjectResponse = {
  id: string;
  title: string;
  genre: string | null;
  tone: string | null;
};

type ProjectStructureResponse = {
  default_branch_id: string | null;
  default_volume_id: string | null;
};

type ChapterResponse = {
  id: string;
  chapter_number: number;
  title: string | null;
  current_version_number: number;
  status: string;
};

function buildUniqueEmail(tag: string): string {
  const token = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  return `story-room-${tag}-${token}@example.com`;
}

async function parseJsonOrThrow<T>(response: Awaited<ReturnType<APIRequestContext["get"]>>): Promise<T> {
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`API ${response.url()} failed: ${response.status()} ${body}`);
  }
  return (await response.json()) as T;
}

async function registerUser(
  request: APIRequestContext,
  tag: string,
): Promise<{ email: string; password: string; session: TokenResponse }> {
  const email = buildUniqueEmail(tag);
  const response = await request.post(`${API_BASE_URL}/api/v1/auth/register`, {
    data: {
      email,
      password: DEFAULT_PASSWORD,
    },
  });
  const session = await parseJsonOrThrow<TokenResponse>(response);
  return {
    email,
    password: DEFAULT_PASSWORD,
    session,
  };
}

async function createProject(
  request: APIRequestContext,
  session: TokenResponse,
  overrides: Partial<Pick<ProjectResponse, "title" | "genre" | "tone">> = {},
): Promise<ProjectResponse> {
  const response = await request.post(`${API_BASE_URL}/api/v1/projects`, {
    data: {
      title: overrides.title ?? `冒烟测试-${Date.now()}`,
      genre: overrides.genre ?? "都市异能",
      tone: overrides.tone ?? "凌厉",
    },
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
  });
  return await parseJsonOrThrow<ProjectResponse>(response);
}

async function getProjectStructure(
  request: APIRequestContext,
  session: TokenResponse,
  projectId: string,
): Promise<ProjectStructureResponse> {
  const response = await request.get(`${API_BASE_URL}/api/v1/projects/${projectId}/structure`, {
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
  });
  return await parseJsonOrThrow<ProjectStructureResponse>(response);
}

async function createChapter(
  request: APIRequestContext,
  session: TokenResponse,
  projectId: string,
  payload: {
    chapter_number: number;
    title: string;
    content: string;
    branch_id: string | null;
    volume_id: string | null;
    status?: string;
  },
): Promise<ChapterResponse> {
  const response = await request.post(`${API_BASE_URL}/api/v1/projects/${projectId}/chapters`, {
    data: {
      chapter_number: payload.chapter_number,
      title: payload.title,
      content: payload.content,
      branch_id: payload.branch_id,
      volume_id: payload.volume_id,
      status: payload.status ?? "draft",
    },
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
  });
  return await parseJsonOrThrow<ChapterResponse>(response);
}

async function patchChapter(
  request: APIRequestContext,
  session: TokenResponse,
  projectId: string,
  chapterId: string,
  payload: Record<string, unknown>,
): Promise<ChapterResponse> {
  const response = await request.patch(
    `${API_BASE_URL}/api/v1/projects/${projectId}/story-engine/chapters/${chapterId}`,
    {
      data: payload,
      headers: {
        Authorization: `Bearer ${session.access_token}`,
      },
    },
  );
  return await parseJsonOrThrow<ChapterResponse>(response);
}

function getVisibleStageCard(page: Page, stage: "outline" | "draft" | "final" | "knowledge") {
  return page.locator(`[data-testid="story-room-stage-card-${stage}"]:visible`).first();
}

const apiFailuresByPage = new WeakMap<Page, string[]>();

test.beforeEach(async ({ page }) => {
  const failures: string[] = [];
  apiFailuresByPage.set(page, failures);
  page.on("response", async (response) => {
    const url = response.url();
    if (!url.startsWith(API_V1_PREFIX)) {
      return;
    }
    if (response.status() < 500) {
      return;
    }
    const method = response.request().method();
    const body = await response.text().catch(() => "<response body unavailable>");
    failures.push(`${method} ${url} -> ${response.status()} ${body.slice(0, 400)}`);
  });
});

test.afterEach(async ({ page }) => {
  const failures = apiFailuresByPage.get(page) ?? [];
  expect(
    failures,
    `Unexpected API 5xx responses observed during UI test:\n${failures.join("\n")}`,
  ).toEqual([]);
});

async function seedAuthSession(page: Page, session: TokenResponse): Promise<void> {
  await page.context().addCookies([
    {
      name: AUTH_COOKIE_KEY,
      value: session.access_token,
      url: FRONTEND_BASE_URL,
    },
  ]);
  await page.addInitScript(
    ([storageKey, serializedSession]) => {
      window.localStorage.setItem(storageKey, serializedSession);
    },
    [AUTH_STORAGE_KEY, JSON.stringify(session)],
  );
}

test.describe("story room smoke", () => {
  test("homepage -> register -> create book -> story room outline", async ({ page }) => {
    const email = buildUniqueEmail("ui-register");

    await page.goto("/");
    await expect(page.getByTestId("home-page")).toBeVisible();

    await page.getByTestId("home-create-book-link").click();
    await expect(page.getByTestId("register-page")).toBeVisible();

    await page.getByTestId("register-email-input").fill(email);
    await page.getByTestId("register-password-input").fill(DEFAULT_PASSWORD);
    await page.getByTestId("register-submit").click();

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 45_000 });
    await expect(page.getByTestId("dashboard-page")).toBeVisible({ timeout: 45_000 });

    await page.getByTestId("dashboard-create-book-title").fill("海城夜潮");
    await page.getByTestId("dashboard-create-book-total-words").fill("900000");
    await page.getByTestId("dashboard-create-book-chapter-words").fill("3000");
    await page.getByTestId("dashboard-create-book-genre").fill("都市异能");
    await page.getByTestId("dashboard-create-book-tone").fill("冷峻");
    await page.getByTestId("dashboard-create-book-submit").click();

    await expect(page).toHaveURL(/\/dashboard\/projects\/[^/]+\/story-room/, {
      timeout: 45_000,
    });
    await expect(page.getByTestId("story-room-page")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("story-room-stage-outline")).toBeVisible({ timeout: 45_000 });
  });

  test("homepage -> login -> dashboard", async ({ page, request }) => {
    const account = await registerUser(request, "ui-login");

    await page.goto("/");
    await expect(page.getByTestId("home-page")).toBeVisible();

    await page.getByTestId("home-login-link").click();
    await expect(page.getByTestId("login-page")).toBeVisible();

    await page.getByTestId("login-email-input").fill(account.email);
    await page.getByTestId("login-password-input").fill(account.password);
    await page.getByTestId("login-submit").click();

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 45_000 });
    await expect(page.getByTestId("dashboard-page")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("dashboard-create-book-form")).toBeVisible();
  });

  test("story room local draft recovery across reload", async ({ page, request }) => {
    const account = await registerUser(request, "local-draft");
    const project = await createProject(request, account.session, {
      title: "本机保稿验证",
    });
    const structure = await getProjectStructure(request, account.session, project.id);
    await createChapter(request, account.session, project.id, {
      chapter_number: 1,
      title: "第一章 夜色将至",
      content: "",
      branch_id: structure.default_branch_id,
      volume_id: structure.default_volume_id,
    });

    await seedAuthSession(page, account.session);
    await page.goto(`/dashboard/projects/${project.id}/story-room?chapter=1`);

    await expect(page.getByTestId("story-room-page")).toBeVisible({ timeout: 45_000 });
    await expect(getVisibleStageCard(page, "draft")).toBeVisible({ timeout: 45_000 });
    await getVisibleStageCard(page, "draft").click();

    await expect(page.getByTestId("story-room-stage-draft")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("draft-editor-surface")).toBeVisible({ timeout: 45_000 });

    await page.getByTestId("draft-chapter-title-input").fill("第一章 夜色将至");
    await page.getByTestId("draft-editor-surface").fill("这是一次本机暂存恢复测试内容。");

    await expect(page.getByText("本机已暂存")).toBeVisible({ timeout: 8_000 });

    await page.reload();

    await expect(page.getByTestId("story-room-page")).toBeVisible({ timeout: 45_000 });
    await expect(getVisibleStageCard(page, "draft")).toBeVisible({ timeout: 45_000 });
    await getVisibleStageCard(page, "draft").click();

    await expect(page.getByTestId("story-room-stage-draft")).toBeVisible({ timeout: 45_000 });
    const restoreLocalDraftButton = page
      .locator('[data-testid="draft-restore-local"]:visible')
      .first();
    await expect(restoreLocalDraftButton).toBeVisible({ timeout: 10_000 });

    await restoreLocalDraftButton.click();

    await expect(page.getByTestId("draft-chapter-title-input")).toHaveValue("第一章 夜色将至");
    const restoredDraftEditor = page
      .locator('[data-testid="draft-editor-surface"]:visible')
      .first();
    await expect(restoredDraftEditor).toBeVisible({ timeout: 15_000 });
    await expect(restoredDraftEditor).toContainText("本机暂存恢复测试内容");
  });

  test("final stage can continue to next chapter", async ({ page, request }) => {
    const account = await registerUser(request, "next-chapter");
    const project = await createProject(request, account.session, {
      title: "终稿续章验证",
    });
    const structure = await getProjectStructure(request, account.session, project.id);
    const chapter = await createChapter(request, account.session, project.id, {
      chapter_number: 1,
      title: "第一章 起势",
      content: "海风撞进旧码头时，少年第一次听见体内的潮声。",
      branch_id: structure.default_branch_id,
      volume_id: structure.default_volume_id,
    });
    await createChapter(request, account.session, project.id, {
      chapter_number: 2,
      title: "第二章 承接",
      content: "",
      branch_id: structure.default_branch_id,
      volume_id: structure.default_volume_id,
    });

    await patchChapter(request, account.session, project.id, chapter.id, {
      status: "review",
      change_reason: "Playwright E2E seed review chapter",
      expected_current_version_number: chapter.current_version_number,
      create_version: false,
    });

    await patchChapter(request, account.session, project.id, chapter.id, {
      status: "final",
      change_reason: "Playwright E2E seed final chapter",
      expected_current_version_number: chapter.current_version_number,
      create_version: false,
      quality_metrics: {
        evaluation_status: "fresh",
        evaluation_updated_at: new Date().toISOString(),
        overall_score: 92,
        heuristic_overall_score: 90,
        ai_taste_score: 14,
        summary: "Playwright seeded a fresh evaluation snapshot for final-stage smoke.",
        story_bible_integrity_issue_count: 0,
        story_bible_integrity_blocking_issue_count: 0,
        canon_issue_count: 0,
        canon_blocking_issue_count: 0,
      },
    });

    await seedAuthSession(page, account.session);
    await page.goto(`/dashboard/projects/${project.id}/story-room?chapter=1`);

    await expect(page.getByTestId("story-room-page")).toBeVisible({ timeout: 45_000 });
    await expect(getVisibleStageCard(page, "final")).toBeVisible({ timeout: 45_000 });
    await getVisibleStageCard(page, "final").click();

    await expect(page.getByTestId("story-room-stage-final")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("final-publish-panel")).toBeVisible({ timeout: 45_000 });
    await expect(page.getByTestId("final-continue-next-chapter")).toBeVisible({
      timeout: 45_000,
    });

    await page.getByTestId("final-continue-next-chapter").click();

    await expect(page.getByTestId("story-room-stage-draft")).toBeVisible();
    await expect(page.getByTestId("draft-chapter-number-input")).toHaveValue("2");
  });
});
