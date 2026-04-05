from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
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
    created_at: datetime = field(default_factory=datetime.utcnow)


class L3LongTermMemory:
    _instance: L3LongTermMemory | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._store: dict[str, KnowledgeEntry] = {}

    @classmethod
    def get_instance(cls) -> L3LongTermMemory:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = L3LongTermMemory()
        return cls._instance

    def store(self, entry: KnowledgeEntry) -> None:
        key = f"{entry.knowledge_type.value}:{entry.id}"
        self._store[key] = entry

    def retrieve(
        self,
        knowledge_type: KnowledgeType | None = None,
        tags: list[str] | None = None,
        min_importance: float = 0.0,
    ) -> list[KnowledgeEntry]:
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
        self._store.clear()


l3_long_term_memory = L3LongTermMemory.get_instance()
