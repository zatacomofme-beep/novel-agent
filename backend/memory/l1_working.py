from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class WorkingMemoryEntry:
    chapter_id: UUID
    chapter_number: int
    content_hash: str
    summary: str
    key_events: list[str]
    active_characters: list[str]
    open_threads: list[str]
    tone_mood: str
    word_count: int
    created_at: datetime = field(default_factory=datetime.utcnow)


class L1WorkingMemory:
    _instance: L1WorkingMemory | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self.entries: dict[UUID, WorkingMemoryEntry] = {}
        self.active_chapter_id: UUID | None = None
        self.current_session_events: list[str] = []

    @classmethod
    def get_instance(cls) -> L1WorkingMemory:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = L1WorkingMemory()
        return cls._instance

    def store(self, entry: WorkingMemoryEntry) -> None:
        self.entries[entry.chapter_id] = entry
        self.active_chapter_id = entry.chapter_id

    def get(self, chapter_id: UUID) -> WorkingMemoryEntry | None:
        return self.entries.get(chapter_id)

    def get_active(self) -> WorkingMemoryEntry | None:
        if self.active_chapter_id:
            return self.entries.get(self.active_chapter_id)
        return None

    def get_recent(self, limit: int = 3) -> list[WorkingMemoryEntry]:
        sorted_entries = sorted(
            self.entries.values(),
            key=lambda e: e.created_at,
            reverse=True,
        )
        return sorted_entries[:limit]

    def add_session_event(self, event: str) -> None:
        self.current_session_events.append(event)

    def clear_session(self) -> None:
        self.current_session_events.clear()

    def clear(self) -> None:
        self.entries.clear()
        self.active_chapter_id = None
        self.current_session_events.clear()


l1_working_memory = L1WorkingMemory.get_instance()
