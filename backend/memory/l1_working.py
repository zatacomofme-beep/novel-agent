from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class L1WorkingMemory:
    _instance: L1WorkingMemory | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, max_entries: int = 100) -> None:
        self._entries: OrderedDict[UUID, WorkingMemoryEntry] = OrderedDict()
        self.active_chapter_id: UUID | None = None
        self.current_session_events: list[str] = []
        self.max_entries = max_entries
        self._write_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> L1WorkingMemory:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = L1WorkingMemory()
        return cls._instance

    def store(self, entry: WorkingMemoryEntry) -> None:
        with self._write_lock:
            if entry.chapter_id in self._entries:
                self._entries.move_to_end(entry.chapter_id)
            self._entries[entry.chapter_id] = entry
            while len(self._entries) > self.max_entries:
                oldest_key = next(iter(self._entries))
                del self._entries[oldest_key]
            self.active_chapter_id = entry.chapter_id

    def get(self, chapter_id: UUID) -> WorkingMemoryEntry | None:
        with self._write_lock:
            if chapter_id in self._entries:
                self._entries.move_to_end(chapter_id)
                return self._entries[chapter_id]
            return None

    def get_active(self) -> WorkingMemoryEntry | None:
        with self._write_lock:
            if self.active_chapter_id and self.active_chapter_id in self._entries:
                return self._entries[self.active_chapter_id]
            return None

    def get_recent(self, limit: int = 3) -> list[WorkingMemoryEntry]:
        with self._write_lock:
            items = list(reversed(list(self._entries.values())))
            return items[:limit]

    def add_session_event(self, event: str) -> None:
        with self._write_lock:
            self.current_session_events.append(event)
            max_events = 1000
            if len(self.current_session_events) > max_events:
                self.current_session_events = self.current_session_events[-max_events:]

    def clear_session(self) -> None:
        with self._write_lock:
            self.current_session_events.clear()

    def clear(self) -> None:
        with self._write_lock:
            self._entries.clear()
            self.active_chapter_id = None
            self.current_session_events.clear()

    @property
    def size(self) -> int:
        return len(self._entries)


l1_working_memory = L1WorkingMemory.get_instance()
