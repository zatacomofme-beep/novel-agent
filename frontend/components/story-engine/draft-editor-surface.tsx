"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
  type MutableRefObject,
} from "react";

import {
  type DraftEditorHandle,
  type DraftEditorSelection,
  EMPTY_DRAFT_SELECTION,
  normalizeEditorText,
  readEditorSelection,
  setEditorSelectionRange,
} from "@/components/story-engine/draft-editor-handle";
import { buildOutlineNodes, hashText } from "@/components/story-engine/outline-node-utils";

type DraftEditorSurfaceProps = {
  value: string;
  disabled: boolean;
  placeholder: string;
  editorRef: MutableRefObject<DraftEditorHandle | null>;
  outlineTitle: string | null;
  outlineContent: string | null;
  onChange: (value: string) => void;
  onLocateSelectionInKnowledge?: (selectionText: string) => void;
};

type PreviewBlock =
  | { key: string; type: "scene_break" }
  | { key: string; type: "paragraph"; content: string };

function buildPreviewBlocks(value: string): PreviewBlock[] {
  return value
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item, index) => {
      if (item === "***" || item === "——" || item === "---") {
        return {
          key: `scene-break-${index}`,
          type: "scene_break" as const,
        };
      }
      return {
        key: `paragraph-${index}`,
        type: "paragraph" as const,
        content: item,
      };
    });
}

function clampSelection(selection: DraftEditorSelection, fallbackLength: number) {
  const selectionStart = selection.start ?? fallbackLength;
  const selectionEnd = selection.end ?? selectionStart;
  return {
    selectionStart,
    selectionEnd,
    selectedText:
      selection.start !== null && selection.end !== null && selection.end > selection.start
        ? selection.text
        : "",
  };
}

export function DraftEditorSurface({
  value,
  disabled,
  placeholder,
  editorRef,
  outlineTitle,
  outlineContent,
  onChange,
  onLocateSelectionInKnowledge,
}: DraftEditorSurfaceProps) {
  const editorDomRef = useRef<HTMLDivElement>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [editorFocused, setEditorFocused] = useState(false);
  const [selection, setSelection] = useState<DraftEditorSelection>(EMPTY_DRAFT_SELECTION);
  const [focusedNodeKey, setFocusedNodeKey] = useState<string | null>(null);
  const [completedNodeKeys, setCompletedNodeKeys] = useState<string[]>([]);

  const previewBlocks = useMemo(() => buildPreviewBlocks(value), [value]);
  const outlineNodes = useMemo(
    () => buildOutlineNodes(outlineTitle, outlineContent),
    [outlineContent, outlineTitle],
  );
  const outlineChecklistStorageKey = useMemo(() => {
    const signature = `${outlineTitle ?? ""}\n${outlineContent ?? ""}`.trim();
    if (!signature) {
      return null;
    }
    return `story-room:outline-checklist:${hashText(signature)}`;
  }, [outlineContent, outlineTitle]);
  const completedNodeSet = useMemo(() => new Set(completedNodeKeys), [completedNodeKeys]);
  const focusedNode = useMemo(
    () => outlineNodes.find((item) => item.key === focusedNodeKey) ?? null,
    [focusedNodeKey, outlineNodes],
  );
  const completedNodeCount = outlineNodes.filter((item) => completedNodeSet.has(item.key)).length;
  const nextNode = useMemo(() => {
    if (!focusedNode) {
      return null;
    }
    const currentIndex = outlineNodes.findIndex((item) => item.key === focusedNode.key);
    if (currentIndex < 0) {
      return null;
    }
    return (
      outlineNodes.slice(currentIndex + 1).find((item) => !completedNodeSet.has(item.key)) ??
      outlineNodes[currentIndex + 1] ??
      null
    );
  }, [completedNodeSet, focusedNode, outlineNodes]);
  const characterCount = value.trim().length;
  const paragraphCount = previewBlocks.filter((item) => item.type === "paragraph").length;
  const readingMinutes = Math.max(1, Math.ceil(characterCount / 900));
  const selectedCount = selection.text.trim().length;
  const showSidebar = previewOpen && !focusMode;

  useEffect(() => {
    const editor = editorDomRef.current;
    if (!editor) {
      return;
    }
    const currentValue = normalizeEditorText(editor.textContent ?? "");
    if (currentValue !== value) {
      editor.textContent = value;
    }
  }, [value]);

  useEffect(() => {
    editorRef.current = {
      focus: () => {
        editorDomRef.current?.focus();
      },
      getSelection: () => readEditorSelection(editorDomRef.current),
      setSelectionRange: (start, end) => {
        const editor = editorDomRef.current;
        if (!editor) {
          return;
        }
        editor.focus();
        setEditorSelectionRange(editor, start, end);
      },
    };

    return () => {
      editorRef.current = null;
    };
  }, [editorRef]);

  useEffect(() => {
    const syncSelection = () => {
      setSelection(readEditorSelection(editorDomRef.current));
    };

    syncSelection();
    document.addEventListener("selectionchange", syncSelection);
    return () => {
      document.removeEventListener("selectionchange", syncSelection);
    };
  }, []);

  useEffect(() => {
    setSelection(readEditorSelection(editorDomRef.current));
  }, [value]);

  useEffect(() => {
    if (!outlineChecklistStorageKey) {
      setCompletedNodeKeys([]);
      return;
    }

    try {
      const rawValue = window.localStorage.getItem(outlineChecklistStorageKey);
      if (!rawValue) {
        setCompletedNodeKeys([]);
        return;
      }
      const parsed = JSON.parse(rawValue);
      if (!Array.isArray(parsed)) {
        setCompletedNodeKeys([]);
        return;
      }
      const nextKeys = parsed.filter((item): item is string =>
        typeof item === "string" && outlineNodes.some((node) => node.key === item),
      );
      setCompletedNodeKeys(nextKeys);
    } catch (err) {
      console.warn("[draft-editor] Failed to parse outline checklist:", err);
      setCompletedNodeKeys([]);
    }
  }, [outlineChecklistStorageKey, outlineNodes]);

  useEffect(() => {
    if (!outlineChecklistStorageKey) {
      return;
    }
    try {
      window.localStorage.setItem(outlineChecklistStorageKey, JSON.stringify(completedNodeKeys));
    } catch (err) {
      console.warn("[draft-editor] Failed to save outline checklist:", err);
    }
  }, [completedNodeKeys, outlineChecklistStorageKey]);

  useEffect(() => {
    if (outlineNodes.length === 0) {
      setFocusedNodeKey(null);
      return;
    }

    const firstAvailableNode =
      outlineNodes.find((item) => !completedNodeSet.has(item.key)) ?? outlineNodes[outlineNodes.length - 1];

    setFocusedNodeKey((current) => {
      if (!current) {
        return firstAvailableNode.key;
      }
      const stillExists = outlineNodes.some((item) => item.key === current);
      if (!stillExists || completedNodeSet.has(current)) {
        return firstAvailableNode.key;
      }
      return current;
    });
  }, [completedNodeSet, outlineNodes]);

  function scheduleSelectionRestore(start: number, end: number) {
    window.requestAnimationFrame(() => {
      editorRef.current?.setSelectionRange(start, end);
    });
  }

  function applyTextMutation(
    transform: (payload: {
      currentValue: string;
      selectionStart: number;
      selectionEnd: number;
      selectedText: string;
    }) => {
      nextValue: string;
      nextSelectionStart: number;
      nextSelectionEnd: number;
    },
  ) {
    const currentSelection = editorRef.current?.getSelection() ?? EMPTY_DRAFT_SELECTION;
    const { selectionStart, selectionEnd, selectedText } = clampSelection(currentSelection, value.length);
    const result = transform({
      currentValue: value,
      selectionStart,
      selectionEnd,
      selectedText,
    });

    onChange(result.nextValue);
    scheduleSelectionRestore(result.nextSelectionStart, result.nextSelectionEnd);
  }

  function handleToggleNodeCompletion(nodeKey: string) {
    const alreadyCompleted = completedNodeSet.has(nodeKey);
    setCompletedNodeKeys((current) =>
      alreadyCompleted ? current.filter((item) => item !== nodeKey) : [...current, nodeKey],
    );

    if (!alreadyCompleted) {
      const currentIndex = outlineNodes.findIndex((item) => item.key === nodeKey);
      const nextAvailableNode =
        outlineNodes.slice(currentIndex + 1).find((item) => !completedNodeSet.has(item.key)) ??
        outlineNodes[currentIndex + 1] ??
        null;
      if (nextAvailableNode) {
        setFocusedNodeKey(nextAvailableNode.key);
      }
    }
  }

  function handleEditorInput() {
    const editor = editorDomRef.current;
    if (!editor) {
      return;
    }
    const nextValue = normalizeEditorText(editor.textContent ?? "");
    if (nextValue !== value) {
      onChange(nextValue);
    }
  }

  function handleEditorKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (disabled) {
      event.preventDefault();
      return;
    }

    if (event.key === "Enter" && !event.nativeEvent.isComposing) {
      event.preventDefault();
      applyTextMutation(({ currentValue, selectionStart, selectionEnd }) => {
        const insertion = event.shiftKey ? "\n" : "\n\n";
        const nextValue =
          currentValue.slice(0, selectionStart) +
          insertion +
          currentValue.slice(selectionEnd);
        const nextCaret = selectionStart + insertion.length;
        return {
          nextValue,
          nextSelectionStart: nextCaret,
          nextSelectionEnd: nextCaret,
        };
      });
      return;
    }

    if (event.key === "Tab") {
      event.preventDefault();
      applyTextMutation(({ currentValue, selectionStart, selectionEnd }) => {
        const insertion = "    ";
        const nextValue =
          currentValue.slice(0, selectionStart) +
          insertion +
          currentValue.slice(selectionEnd);
        const nextCaret = selectionStart + insertion.length;
        return {
          nextValue,
          nextSelectionStart: nextCaret,
          nextSelectionEnd: nextCaret,
        };
      });
    }
  }

  function handleEditorPaste(event: ClipboardEvent<HTMLDivElement>) {
    event.preventDefault();
    const pastedText = normalizeEditorText(event.clipboardData.getData("text/plain")).replace(/\r\n/g, "\n");
    if (!pastedText) {
      return;
    }
    applyTextMutation(({ currentValue, selectionStart, selectionEnd }) => {
      const nextValue =
        currentValue.slice(0, selectionStart) +
        pastedText +
        currentValue.slice(selectionEnd);
      const nextCaret = selectionStart + pastedText.length;
      return {
        nextValue,
        nextSelectionStart: nextCaret,
        nextSelectionEnd: nextCaret,
      };
    });
  }

  return (
    <div className="mt-4 rounded-[28px] border border-black/10 bg-[#fdfaf2] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap gap-2 text-xs text-black/55">
          <span className="rounded-full border border-black/10 bg-white px-3 py-1">
            {characterCount > 0 ? `${characterCount} 字` : "还没起稿"}
          </span>
          <span className="rounded-full border border-black/10 bg-white px-3 py-1">
            {paragraphCount > 0 ? `${paragraphCount} 段` : "0 段"}
          </span>
          <span className="rounded-full border border-black/10 bg-white px-3 py-1">
            阅读约 {readingMinutes} 分钟
          </span>
          {outlineNodes.length > 0 ? (
            <span className="rounded-full border border-black/10 bg-white px-3 py-1">
              节点 {completedNodeCount}/{outlineNodes.length}
            </span>
          ) : null}
          {selectedCount > 0 ? (
            <span className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-1 text-copper">
              已选 {selectedCount} 字
            </span>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={disabled}
            onClick={() =>
              applyTextMutation(({ currentValue, selectionStart }) => {
                const insertion = selectionStart === 0 ? "***\n\n" : "\n\n***\n\n";
                const nextValue =
                  currentValue.slice(0, selectionStart) +
                  insertion +
                  currentValue.slice(selectionStart);
                const nextCaret = selectionStart + insertion.length;
                return {
                  nextValue,
                  nextSelectionStart: nextCaret,
                  nextSelectionEnd: nextCaret,
                };
              })
            }
            type="button"
          >
            插入分场
          </button>
          <button
            className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={disabled}
            onClick={() =>
              applyTextMutation(({ currentValue, selectionStart }) => {
                const insertion = "\n\n";
                const nextValue =
                  currentValue.slice(0, selectionStart) +
                  insertion +
                  currentValue.slice(selectionStart);
                const nextCaret = selectionStart + insertion.length;
                return {
                  nextValue,
                  nextSelectionStart: nextCaret,
                  nextSelectionEnd: nextCaret,
                };
              })
            }
            type="button"
          >
            分一段
          </button>
          <button
            className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={disabled}
            onClick={() =>
              applyTextMutation(
                ({ currentValue, selectionStart, selectionEnd, selectedText }) => {
                  const wrapped = `“${selectedText}”`;
                  const nextValue =
                    currentValue.slice(0, selectionStart) +
                    wrapped +
                    currentValue.slice(selectionEnd);
                  const cursorStart = selectionStart + 1;
                  const cursorEnd = cursorStart + selectedText.length;
                  return {
                    nextValue,
                    nextSelectionStart: cursorStart,
                    nextSelectionEnd: selectedText ? cursorEnd : cursorStart,
                  };
                },
              )
            }
            type="button"
          >
            包成对话
          </button>
          <button
            className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
            disabled={disabled || value.length === 0}
            onClick={() => onChange(value.replace(/\n{3,}/g, "\n\n").trimEnd())}
            type="button"
          >
            清理空行
          </button>
          {selectedCount > 0 && onLocateSelectionInKnowledge ? (
            <button
              className="rounded-full border border-copper/20 bg-[#f6ede3] px-3 py-2 text-xs font-semibold text-copper transition hover:opacity-90"
              onClick={() => onLocateSelectionInKnowledge(selection.text)}
              type="button"
            >
              去设定里定位
            </button>
          ) : null}
          <button
            className={`rounded-full border px-3 py-2 text-xs font-semibold transition ${
              focusMode
                ? "border-copper/20 bg-[#f6ede3] text-copper"
                : "border-black/10 bg-white text-black/72 hover:bg-[#f6f0e6]"
            }`}
            onClick={() => {
              setFocusMode((current) => !current);
              if (!focusMode) {
                setPreviewOpen(false);
              }
            }}
            type="button"
          >
            {focusMode ? "退出专注" : "专注写作"}
          </button>
          <button
            className={`rounded-full border px-3 py-2 text-xs font-semibold transition ${
              previewOpen
                ? "border-copper/20 bg-[#f6ede3] text-copper"
                : "border-black/10 bg-white text-black/72 hover:bg-[#f6f0e6]"
            }`}
            onClick={() => {
              setPreviewOpen((current) => !current);
              setFocusMode(false);
            }}
            type="button"
          >
            {showSidebar ? "收起侧栏" : "展开侧栏"}
          </button>
        </div>
      </div>

      <div
        className={`mt-4 grid gap-4 ${showSidebar ? "xl:grid-cols-[minmax(0,1.12fr)_320px]" : ""}`}
      >
        <div className="rounded-[24px] border border-black/10 bg-[radial-gradient(circle_at_top,rgba(244,236,220,0.45),transparent_42%),linear-gradient(180deg,#fbf7f1_0%,#f7f1e6_100%)]">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-black/8 px-4 py-3">
            <p className="text-sm font-semibold text-black/78">正文写作器</p>
            <div className="flex flex-wrap items-center gap-2 text-xs text-black/55">
              <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                回车分段
              </span>
              <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                Shift + Enter 软换行
              </span>
              <span className="rounded-full border border-black/10 bg-white px-3 py-1">
                {disabled ? "当前锁定" : "可自由编辑"}
              </span>
            </div>
          </div>

          {focusedNode ? (
            <div className="px-4 pt-4">
              <div className="rounded-[22px] border border-copper/15 bg-[#fbf3e8] px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] uppercase tracking-[0.18em] text-copper">当前节点</p>
                    <p className="mt-2 text-sm font-semibold text-black/82">
                      节点 {focusedNode.index + 1} · {focusedNode.title}
                    </p>
                    {focusedNode.summary !== focusedNode.title ? (
                      <p className="mt-2 text-sm leading-7 text-black/60">{focusedNode.summary}</p>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    <button
                      className="rounded-full border border-copper/20 bg-white px-3 py-2 text-xs font-semibold text-copper transition hover:bg-[#f7ede1]"
                      disabled={disabled}
                      onClick={() => handleToggleNodeCompletion(focusedNode.key)}
                      type="button"
                    >
                      {completedNodeSet.has(focusedNode.key) ? "撤回写完" : "标记写完"}
                    </button>
                    <button
                      className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6] disabled:cursor-not-allowed disabled:opacity-60"
                      disabled={!nextNode}
                      onClick={() => {
                        if (nextNode) {
                          setFocusedNodeKey(nextNode.key);
                        }
                      }}
                      type="button"
                    >
                      下个节点
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          <div className={`px-4 py-4 ${focusMode ? "xl:px-10 xl:py-8" : ""}`}>
            <div className={`mx-auto ${focusMode ? "max-w-4xl" : "max-w-3xl"}`}>
              <div className="rounded-[30px] border border-[#e9ddca] bg-[#fffdfa] shadow-[0_24px_60px_rgba(57,45,24,0.08)]">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#efe6d7] px-6 py-4">
                  <p className="text-sm font-semibold text-black/78">
                    {focusMode ? "专注模式" : "纸页模式"}
                  </p>
                  <span className="rounded-full border border-[#eadfcd] bg-[#faf4ea] px-3 py-1 text-xs text-black/55">
                    {selectedCount > 0 ? `当前选中 ${selectedCount} 字` : "点击纸页直接开写"}
                  </span>
                </div>

                <div className="relative px-6 py-6 md:px-8 md:py-8">
                  {!value.trim() && !editorFocused ? (
                    <div className="pointer-events-none absolute left-6 right-6 top-6 text-[17px] leading-[2.1] text-black/28 md:left-8 md:right-8 md:top-8">
                      {placeholder}
                    </div>
                  ) : null}

                  <div
                    ref={editorDomRef}
                    contentEditable={!disabled}
                    data-testid="draft-editor-surface"
                    role="textbox"
                    aria-multiline="true"
                    suppressContentEditableWarning
                    spellCheck={false}
                    className="min-h-[720px] whitespace-pre-wrap break-words text-[17px] leading-[2.1] text-black/88 outline-none"
                    onInput={handleEditorInput}
                    onKeyDown={handleEditorKeyDown}
                    onPaste={handleEditorPaste}
                    onFocus={() => setEditorFocused(true)}
                    onBlur={() => setEditorFocused(false)}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {showSidebar ? (
          <aside className="space-y-4">
            <section className="rounded-[24px] border border-black/10 bg-white px-4 py-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-copper">本章节点</p>
                  {outlineTitle ? (
                    <p className="mt-2 text-sm font-semibold text-black/82">{outlineTitle}</p>
                  ) : null}
                </div>
                {outlineNodes.length > 0 ? (
                  <span className="rounded-full border border-black/10 bg-[#fbfaf5] px-3 py-1 text-xs text-black/55">
                    {completedNodeCount}/{outlineNodes.length}
                  </span>
                ) : null}
              </div>

              {outlineNodes.length > 0 ? (
                <div className="mt-4 space-y-3">
                  {outlineNodes.map((node) => {
                    const isActive = focusedNodeKey === node.key;
                    const isCompleted = completedNodeSet.has(node.key);
                    const tone = isCompleted
                      ? "border-emerald-200 bg-emerald-50"
                      : isActive
                        ? "border-copper/20 bg-[#fbf3e8]"
                        : "border-black/10 bg-[#fbfaf5]";

                    return (
                      <div
                        key={node.key}
                        className={`rounded-[20px] border px-4 py-4 transition ${tone}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <p className="text-[11px] uppercase tracking-[0.16em] text-black/42">
                              节点 {node.index + 1}
                            </p>
                            <p className="mt-1 text-sm font-semibold text-black/82">{node.title}</p>
                            {node.summary !== node.title ? (
                              <p className="mt-2 text-xs leading-6 text-black/58">{node.summary}</p>
                            ) : null}
                          </div>
                          <span
                            className={`rounded-full border px-2.5 py-1 text-[11px] ${
                              isCompleted
                                ? "border-emerald-200 bg-white text-emerald-700"
                                : isActive
                                  ? "border-copper/20 bg-white text-copper"
                                  : "border-black/10 bg-white text-black/52"
                            }`}
                          >
                            {isCompleted ? "写完" : isActive ? "当前" : "待写"}
                          </span>
                        </div>

                        <div className="mt-3 flex flex-wrap gap-2">
                          <button
                            className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                            onClick={() => setFocusedNodeKey(node.key)}
                            type="button"
                          >
                            {isActive ? "正在写" : "写这个"}
                          </button>
                          <button
                            className="rounded-full border border-black/10 bg-white px-3 py-2 text-xs font-semibold text-black/72 transition hover:bg-[#f6f0e6]"
                            onClick={() => handleToggleNodeCompletion(node.key)}
                            type="button"
                          >
                            {isCompleted ? "撤回" : "标记写完"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="mt-3 text-sm text-black/50">先绑定三级大纲。</p>
              )}
            </section>

            <section className="rounded-[24px] border border-black/10 bg-white px-4 py-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-black/82">排版预览</p>
                <span className="text-xs text-black/45">
                  {previewBlocks.length > 0 ? `${previewBlocks.length} 个块` : "暂无内容"}
                </span>
              </div>

              <div className="mt-4 max-h-[620px] space-y-4 overflow-y-auto pr-1">
                {previewBlocks.length > 0 ? (
                  previewBlocks.map((block) =>
                    block.type === "scene_break" ? (
                      <div
                        key={block.key}
                        className="flex items-center justify-center py-2 text-black/25"
                      >
                        <span className="tracking-[0.48em]">***</span>
                      </div>
                    ) : (
                      <p
                        key={block.key}
                        className="text-sm leading-8 text-black/72"
                      >
                        {block.content}
                      </p>
                    ),
                  )
                ) : (
                  <div className="rounded-[20px] border border-dashed border-black/10 bg-[#fbfaf5] px-4 py-6 text-sm text-black/48">
                    写下第一段后，这里会显示预览。
                  </div>
                )}
              </div>
            </section>
          </aside>
        ) : null}
      </div>
    </div>
  );
}
