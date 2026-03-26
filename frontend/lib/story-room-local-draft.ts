"use client";

export type StoryRoomLocalDraftScope = {
  projectId: string;
  branchId: string | null;
  volumeId: string | null;
  chapterNumber: number;
};

export type StoryRoomLocalDraftSnapshot = StoryRoomLocalDraftScope & {
  chapterTitle: string;
  draftText: string;
  outlineId: string | null;
  sourceChapterId: string | null;
  sourceVersionNumber: number | null;
  updatedAt: string;
};

export type StoryRoomLocalDraftSummary = StoryRoomLocalDraftScope & {
  storageKey: string;
  chapterTitle: string;
  outlineId: string | null;
  sourceChapterId: string | null;
  sourceVersionNumber: number | null;
  updatedAt: string;
  excerpt: string;
  charCount: number;
  storageEngine: "indexeddb" | "localStorage";
};

export type StoryRoomLocalDraftBaseline = {
  chapterId: string | null;
  chapterTitle: string;
  draftText: string;
  currentVersionNumber: number | null;
};

export type StoryRoomLocalDraftRecoveryState =
  | "unchanged"
  | "clean"
  | "server_newer"
  | "local_newer"
  | "relinked";

export type StoryRoomLocalDraftRecoveryAssessment = {
  canRestore: boolean;
  state: StoryRoomLocalDraftRecoveryState;
};

type StoryRoomLocalDraftRecord = StoryRoomLocalDraftSnapshot & {
  storageKey: string;
};

const STORY_ROOM_LOCAL_DRAFT_PREFIX = "story-room.local-draft";
const STORY_ROOM_LOCAL_DRAFT_DB_NAME = "story-room-local-draft-db";
const STORY_ROOM_LOCAL_DRAFT_STORE_NAME = "drafts";
const STORY_ROOM_LOCAL_DRAFT_DB_VERSION = 1;

let storyRoomLocalDraftDatabasePromise: Promise<IDBDatabase | null> | null = null;

function normalizeKeyPart(value: string | null | undefined): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : "default";
}

function parseStoryRoomLocalDraftSnapshot(
  value: unknown,
): StoryRoomLocalDraftSnapshot | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const parsed = value as Partial<StoryRoomLocalDraftSnapshot>;
  if (
    typeof parsed.projectId !== "string" ||
    typeof parsed.chapterNumber !== "number" ||
    typeof parsed.chapterTitle !== "string" ||
    typeof parsed.draftText !== "string" ||
    typeof parsed.updatedAt !== "string"
  ) {
    return null;
  }

  return {
    projectId: parsed.projectId,
    branchId: typeof parsed.branchId === "string" ? parsed.branchId : null,
    volumeId: typeof parsed.volumeId === "string" ? parsed.volumeId : null,
    chapterNumber: parsed.chapterNumber,
    chapterTitle: parsed.chapterTitle,
    draftText: parsed.draftText,
    outlineId: typeof parsed.outlineId === "string" ? parsed.outlineId : null,
    sourceChapterId:
      typeof parsed.sourceChapterId === "string" ? parsed.sourceChapterId : null,
    sourceVersionNumber:
      typeof parsed.sourceVersionNumber === "number" ? parsed.sourceVersionNumber : null,
    updatedAt: parsed.updatedAt,
  };
}

function parseStoryRoomLocalDraftRecord(
  value: unknown,
): StoryRoomLocalDraftRecord | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const parsed = value as Partial<StoryRoomLocalDraftRecord>;
  if (typeof parsed.storageKey !== "string") {
    return null;
  }

  const snapshot = parseStoryRoomLocalDraftSnapshot(parsed);
  if (!snapshot) {
    return null;
  }

  return {
    storageKey: parsed.storageKey,
    ...snapshot,
  };
}

function buildStoryRoomLocalDraftRecord(
  storageKey: string,
  snapshot: StoryRoomLocalDraftSnapshot,
): StoryRoomLocalDraftRecord {
  return {
    storageKey,
    ...snapshot,
  };
}

function buildDraftExcerpt(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= 44) {
    return normalized;
  }
  return `${normalized.slice(0, 44)}...`;
}

function parseLegacyLocalDraft(
  storageKey: string,
): StoryRoomLocalDraftRecord | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) {
      return null;
    }
    const snapshot = parseStoryRoomLocalDraftSnapshot(JSON.parse(raw));
    if (!snapshot) {
      return null;
    }
    return buildStoryRoomLocalDraftRecord(storageKey, snapshot);
  } catch {
    return null;
  }
}

function parseLegacyProjectLocalDrafts(
  projectId: string,
): StoryRoomLocalDraftRecord[] {
  if (typeof window === "undefined") {
    return [];
  }

  const drafts: StoryRoomLocalDraftRecord[] = [];
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const storageKey = window.localStorage.key(index);
    if (!storageKey || !storageKey.startsWith(STORY_ROOM_LOCAL_DRAFT_PREFIX)) {
      continue;
    }
    const draft = parseLegacyLocalDraft(storageKey);
    if (!draft || draft.projectId !== projectId) {
      continue;
    }
    drafts.push(draft);
  }
  return drafts;
}

function requestToPromise<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function waitForTransaction(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error);
  });
}

async function openStoryRoomLocalDraftDatabase(): Promise<IDBDatabase | null> {
  if (typeof window === "undefined" || typeof window.indexedDB === "undefined") {
    return null;
  }

  if (!storyRoomLocalDraftDatabasePromise) {
    storyRoomLocalDraftDatabasePromise = new Promise((resolve) => {
      const request = window.indexedDB.open(
        STORY_ROOM_LOCAL_DRAFT_DB_NAME,
        STORY_ROOM_LOCAL_DRAFT_DB_VERSION,
      );

      request.onupgradeneeded = () => {
        const database = request.result;
        const store = database.objectStoreNames.contains(STORY_ROOM_LOCAL_DRAFT_STORE_NAME)
          ? request.transaction?.objectStore(STORY_ROOM_LOCAL_DRAFT_STORE_NAME) ?? null
          : database.createObjectStore(STORY_ROOM_LOCAL_DRAFT_STORE_NAME, {
              keyPath: "storageKey",
            });
        if (store && !store.indexNames.contains("projectId")) {
          store.createIndex("projectId", "projectId", { unique: false });
        }
      };

      request.onsuccess = () => {
        const database = request.result;
        database.onversionchange = () => database.close();
        resolve(database);
      };

      request.onerror = () => resolve(null);
      request.onblocked = () => resolve(null);
    });
  }

  return storyRoomLocalDraftDatabasePromise;
}

async function readIndexedDbLocalDraft(
  storageKey: string,
): Promise<StoryRoomLocalDraftRecord | null> {
  const database = await openStoryRoomLocalDraftDatabase();
  if (!database) {
    return null;
  }

  try {
    const transaction = database.transaction(STORY_ROOM_LOCAL_DRAFT_STORE_NAME, "readonly");
    const store = transaction.objectStore(STORY_ROOM_LOCAL_DRAFT_STORE_NAME);
    const result = await requestToPromise(store.get(storageKey));
    return parseStoryRoomLocalDraftRecord(result);
  } catch {
    return null;
  }
}

async function writeIndexedDbLocalDraft(record: StoryRoomLocalDraftRecord): Promise<boolean> {
  const database = await openStoryRoomLocalDraftDatabase();
  if (!database) {
    return false;
  }

  try {
    const transaction = database.transaction(STORY_ROOM_LOCAL_DRAFT_STORE_NAME, "readwrite");
    transaction.objectStore(STORY_ROOM_LOCAL_DRAFT_STORE_NAME).put(record);
    await waitForTransaction(transaction);
    return true;
  } catch {
    return false;
  }
}

async function removeIndexedDbLocalDraft(storageKey: string): Promise<void> {
  const database = await openStoryRoomLocalDraftDatabase();
  if (!database) {
    return;
  }

  try {
    const transaction = database.transaction(STORY_ROOM_LOCAL_DRAFT_STORE_NAME, "readwrite");
    transaction.objectStore(STORY_ROOM_LOCAL_DRAFT_STORE_NAME).delete(storageKey);
    await waitForTransaction(transaction);
  } catch {
    // 写作保护是兜底能力，删除失败时不阻断主流程。
  }
}

async function listIndexedDbLocalDrafts(
  projectId: string,
): Promise<StoryRoomLocalDraftRecord[]> {
  const database = await openStoryRoomLocalDraftDatabase();
  if (!database) {
    return [];
  }

  try {
    const transaction = database.transaction(STORY_ROOM_LOCAL_DRAFT_STORE_NAME, "readonly");
    const store = transaction.objectStore(STORY_ROOM_LOCAL_DRAFT_STORE_NAME);
    const index = store.index("projectId");
    const records = await requestToPromise(index.getAll(projectId));
    return records
      .map((item) => parseStoryRoomLocalDraftRecord(item))
      .filter((item): item is StoryRoomLocalDraftRecord => item !== null);
  } catch {
    return [];
  }
}

async function migrateLegacyLocalDraftRecord(
  record: StoryRoomLocalDraftRecord,
): Promise<void> {
  const migrated = await writeIndexedDbLocalDraft(record);
  if (!migrated || typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(record.storageKey);
}

export function buildStoryRoomLocalDraftKey(scope: StoryRoomLocalDraftScope): string {
  return [
    STORY_ROOM_LOCAL_DRAFT_PREFIX,
    normalizeKeyPart(scope.projectId),
    normalizeKeyPart(scope.branchId),
    normalizeKeyPart(scope.volumeId),
    String(scope.chapterNumber),
  ].join(":");
}

export function summarizeStoryRoomLocalDraft(
  storageKey: string,
  snapshot: StoryRoomLocalDraftSnapshot,
  storageEngine: "indexeddb" | "localStorage" = "indexeddb",
): StoryRoomLocalDraftSummary {
  return {
    storageKey,
    projectId: snapshot.projectId,
    branchId: snapshot.branchId,
    volumeId: snapshot.volumeId,
    chapterNumber: snapshot.chapterNumber,
    chapterTitle: snapshot.chapterTitle,
    outlineId: snapshot.outlineId,
    sourceChapterId: snapshot.sourceChapterId,
    sourceVersionNumber: snapshot.sourceVersionNumber,
    updatedAt: snapshot.updatedAt,
    excerpt: buildDraftExcerpt(snapshot.draftText),
    charCount: snapshot.draftText.trim().length,
    storageEngine,
  };
}

export async function readStoryRoomLocalDraft(
  storageKey: string,
): Promise<StoryRoomLocalDraftSnapshot | null> {
  const indexedRecord = await readIndexedDbLocalDraft(storageKey);
  if (indexedRecord) {
    return parseStoryRoomLocalDraftSnapshot(indexedRecord);
  }

  const legacyRecord = parseLegacyLocalDraft(storageKey);
  if (legacyRecord) {
    void migrateLegacyLocalDraftRecord(legacyRecord);
    return parseStoryRoomLocalDraftSnapshot(legacyRecord);
  }

  return null;
}

export async function writeStoryRoomLocalDraft(
  storageKey: string,
  snapshot: StoryRoomLocalDraftSnapshot,
): Promise<void> {
  if (typeof window === "undefined") {
    return;
  }

  const record = buildStoryRoomLocalDraftRecord(storageKey, snapshot);
  const wroteToIndexedDb = await writeIndexedDbLocalDraft(record);
  if (wroteToIndexedDb) {
    window.localStorage.removeItem(storageKey);
    return;
  }

  window.localStorage.setItem(storageKey, JSON.stringify(snapshot));
}

export async function removeStoryRoomLocalDraft(storageKey: string): Promise<void> {
  if (typeof window === "undefined") {
    return;
  }

  await removeIndexedDbLocalDraft(storageKey);
  window.localStorage.removeItem(storageKey);
}

export async function listStoryRoomLocalDrafts(
  projectId: string,
): Promise<StoryRoomLocalDraftSummary[]> {
  const indexedRecords = await listIndexedDbLocalDrafts(projectId);
  const legacyRecords = parseLegacyProjectLocalDrafts(projectId);
  const mergedRecords = new Map<string, StoryRoomLocalDraftSummary>();

  for (const record of indexedRecords) {
    const snapshot = parseStoryRoomLocalDraftSnapshot(record);
    if (!snapshot) {
      continue;
    }
    mergedRecords.set(
      record.storageKey,
      summarizeStoryRoomLocalDraft(record.storageKey, snapshot, "indexeddb"),
    );
  }

  for (const record of legacyRecords) {
    if (mergedRecords.has(record.storageKey)) {
      continue;
    }
    const snapshot = parseStoryRoomLocalDraftSnapshot(record);
    if (!snapshot) {
      continue;
    }
    mergedRecords.set(
      record.storageKey,
      summarizeStoryRoomLocalDraft(record.storageKey, snapshot, "localStorage"),
    );
    void migrateLegacyLocalDraftRecord(record);
  }

  return Array.from(mergedRecords.values())
    .filter((item) => item.chapterTitle.trim().length > 0 || item.charCount > 0)
    .sort((left, right) => {
      return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime();
    });
}

export function analyzeStoryRoomLocalDraftRecovery(
  snapshot: StoryRoomLocalDraftSnapshot,
  baseline: StoryRoomLocalDraftBaseline,
): StoryRoomLocalDraftRecoveryAssessment {
  const normalizedTitle = baseline.chapterTitle.trim();
  const normalizedDraft = baseline.draftText;

  if (
    snapshot.chapterTitle.trim() === normalizedTitle &&
    snapshot.draftText === normalizedDraft
  ) {
    return {
      canRestore: false,
      state: "unchanged",
    };
  }

  if (
    baseline.chapterId &&
    snapshot.sourceChapterId &&
    snapshot.sourceChapterId !== baseline.chapterId
  ) {
    return {
      canRestore: true,
      state: "relinked",
    };
  }

  if (
    baseline.currentVersionNumber !== null &&
    snapshot.sourceVersionNumber !== null &&
    snapshot.sourceVersionNumber < baseline.currentVersionNumber
  ) {
    return {
      canRestore: true,
      state: "server_newer",
    };
  }

  if (
    baseline.currentVersionNumber !== null &&
    snapshot.sourceVersionNumber !== null &&
    snapshot.sourceVersionNumber > baseline.currentVersionNumber
  ) {
    return {
      canRestore: true,
      state: "local_newer",
    };
  }

  return {
    canRestore: true,
    state: "clean",
  };
}
