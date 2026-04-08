from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


class KnowledgeType(str, Enum):
    WORLD_RULE = "world_rule"
    CHARACTER_ARC = "character_arc"
    PLOT_HISTORY = "plot_history"
    THEME = "theme"
    LOCATION = "location"
    ITEM = "item"
    FACTION = "faction"
    TIMELINE = "timeline"


@dataclass
class KnowledgeEntry:
    id: UUID
    knowledge_type: KnowledgeType
    title: str
    content: str
    chapter_number: int | None
    importance: float
    tags: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class L3LongTermMemory:
    _instance: L3LongTermMemory | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, max_entries: int = 1000) -> None:
        self._store: OrderedDict[str, KnowledgeEntry] = OrderedDict()
        self.max_entries = max_entries
        self._write_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> L3LongTermMemory:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = L3LongTermMemory()
        return cls._instance

    def store(self, entry: KnowledgeEntry) -> None:
        with self._write_lock:
            key = f"{entry.knowledge_type.value}:{entry.id}"
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = entry
            while len(self._store) > self.max_entries:
                oldest_key = next(iter(self._store))
                del self._store[oldest_key]

    def retrieve(
        self,
        knowledge_type: KnowledgeType | None = None,
        tags: list[str] | None = None,
        min_importance: float = 0.0,
    ) -> list[KnowledgeEntry]:
        with self._write_lock:
            results = list(self._store.values())

        if knowledge_type is not None:
            results = [e for e in results if e.knowledge_type == knowledge_type]

        if tags:
            results = [
                e for e in results
                if any(tag in e.tags for tag in tags)
            ]

        results = [e for e in results if e.importance >= min_importance]
        return sorted(results, key=lambda e: (e.importance, e.created_at), reverse=True)

    def get_character_arcs(self) -> list[KnowledgeEntry]:
        return self.retrieve(knowledge_type=KnowledgeType.CHARACTER_ARC)

    def get_world_rules(self) -> list[KnowledgeEntry]:
        return self.retrieve(knowledge_type=KnowledgeType.WORLD_RULE)

    def get_plot_history(self) -> list[KnowledgeEntry]:
        return self.retrieve(knowledge_type=KnowledgeType.PLOT_HISTORY)

    def clear(self) -> None:
        with self._write_lock:
            self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


l3_long_term_memory = L3LongTermMemory.get_instance()
