"use client";

export type DraftEditorSelection = {
  start: number | null;
  end: number | null;
  text: string;
};

export type DraftEditorHandle = {
  focus: () => void;
  getSelection: () => DraftEditorSelection;
  setSelectionRange: (start: number, end: number) => void;
};

export const EMPTY_DRAFT_SELECTION: DraftEditorSelection = {
  start: null,
  end: null,
  text: "",
};

export function normalizeEditorText(value: string): string {
  return value.replace(/\u00a0/g, " ").replace(/\r/g, "");
}

export function readEditorSelection(root: HTMLElement | null): DraftEditorSelection {
  if (!root || typeof window === "undefined") {
    return EMPTY_DRAFT_SELECTION;
  }

  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) {
    return EMPTY_DRAFT_SELECTION;
  }

  const range = selection.getRangeAt(0);
  if (!root.contains(range.startContainer) || !root.contains(range.endContainer)) {
    return EMPTY_DRAFT_SELECTION;
  }

  const startRange = document.createRange();
  startRange.selectNodeContents(root);
  startRange.setEnd(range.startContainer, range.startOffset);

  const endRange = document.createRange();
  endRange.selectNodeContents(root);
  endRange.setEnd(range.endContainer, range.endOffset);

  const start = normalizeEditorText(startRange.toString()).length;
  const end = normalizeEditorText(endRange.toString()).length;
  const text = normalizeEditorText(range.toString());

  if (end <= start || text.trim().length === 0) {
    return {
      start: null,
      end: null,
      text: "",
    };
  }

  return {
    start,
    end,
    text,
  };
}

function findTextPosition(root: HTMLElement, targetOffset: number): {
  node: Text;
  offset: number;
} {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let currentNode = walker.nextNode() as Text | null;
  let remaining = Math.max(0, targetOffset);
  let lastTextNode: Text | null = null;

  while (currentNode) {
    const textLength = currentNode.textContent?.length ?? 0;
    lastTextNode = currentNode;
    if (remaining <= textLength) {
      return {
        node: currentNode,
        offset: remaining,
      };
    }
    remaining -= textLength;
    currentNode = walker.nextNode() as Text | null;
  }

  if (lastTextNode) {
    return {
      node: lastTextNode,
      offset: lastTextNode.textContent?.length ?? 0,
    };
  }

  const fallbackNode = document.createTextNode(root.textContent ?? "");
  root.textContent = "";
  root.appendChild(fallbackNode);
  return {
    node: fallbackNode,
    offset: Math.min(remaining, fallbackNode.textContent?.length ?? 0),
  };
}

export function setEditorSelectionRange(
  root: HTMLElement | null,
  start: number,
  end: number,
): void {
  if (!root || typeof window === "undefined") {
    return;
  }

  const normalizedContent = normalizeEditorText(root.textContent ?? "");
  if (!root.textContent) {
    root.textContent = normalizedContent;
  }

  const startPosition = findTextPosition(root, start);
  const endPosition = findTextPosition(root, end);
  const range = document.createRange();
  range.setStart(startPosition.node, startPosition.offset);
  range.setEnd(endPosition.node, endPosition.offset);

  const selection = window.getSelection();
  if (!selection) {
    return;
  }

  selection.removeAllRanges();
  selection.addRange(range);
}
