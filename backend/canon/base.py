from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Iterable, Optional, Protocol

from pydantic import BaseModel, Field

from memory.story_bible import StoryBibleContext


ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def normalize_alias(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _iter_alias_matches(text: str, alias: str) -> Iterable[re.Match[str]]:
    cleaned = str(alias or "").strip()
    if not cleaned:
        return []
    if ASCII_TOKEN_PATTERN.fullmatch(cleaned):
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(cleaned)}(?![A-Za-z0-9_])", re.IGNORECASE)
        return pattern.finditer(text)
    return re.finditer(re.escape(cleaned), text)


def content_mentions_alias(text: str, alias: str) -> bool:
    return any(_iter_alias_matches(text, alias))


def build_evidence_excerpt(text: str, needle: str, *, radius: int = 22) -> str | None:
    for match in _iter_alias_matches(text, needle):
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        return text[start:end].strip()
    return None


def clean_strings(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        candidate = values.strip()
        return [candidate] if candidate else []
    if not isinstance(values, list):
        return []
    cleaned: list[str] = []
    for item in values:
        if not isinstance(item, str):
            continue
        candidate = item.strip()
        if candidate:
            cleaned.append(candidate)
    return cleaned


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class CanonEntityRef(BaseModel):
    plugin_key: str
    entity_type: str
    entity_id: str
    label: str


class CanonIssue(BaseModel):
    plugin_key: str
    code: str
    dimension: str
    severity: str = "medium"
    blocking: bool = False
    message: str
    expected: Optional[str] = None
    actual: Optional[str] = None
    evidence_text: Optional[str] = None
    fix_hint: Optional[str] = None
    entity_refs: list[CanonEntityRef] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CanonValidationReport(BaseModel):
    chapter_number: int
    chapter_title: Optional[str] = None
    issue_count: int
    blocking_issue_count: int
    plugin_breakdown: dict[str, int] = Field(default_factory=dict)
    referenced_entities: list[CanonEntityRef] = Field(default_factory=list)
    issues: list[CanonIssue] = Field(default_factory=list)
    summary: str


class CanonIntegrityReport(BaseModel):
    issue_count: int
    blocking_issue_count: int
    plugin_breakdown: dict[str, int] = Field(default_factory=dict)
    issues: list[CanonIssue] = Field(default_factory=list)
    summary: str


@dataclass
class CanonEntity:
    plugin_key: str
    entity_type: str
    entity_id: str
    label: str
    aliases: set[str] = field(default_factory=set)
    data: dict[str, Any] = field(default_factory=dict)
    source_payload: dict[str, Any] = field(default_factory=dict)

    def ref(self) -> CanonEntityRef:
        return entity_ref(self)


def entity_ref(entity: CanonEntity) -> CanonEntityRef:
    return CanonEntityRef(
        plugin_key=entity.plugin_key,
        entity_type=entity.entity_type,
        entity_id=entity.entity_id,
        label=entity.label,
    )


@dataclass
class CanonSnapshot:
    story_bible: StoryBibleContext
    chapter_number: int
    chapter_title: str | None
    entities_by_plugin: dict[str, list[CanonEntity]] = field(default_factory=dict)
    entities_by_id: dict[tuple[str, str], CanonEntity] = field(default_factory=dict)
    alias_index: dict[str, list[CanonEntity]] = field(default_factory=dict)

    def add_entity(self, entity: CanonEntity) -> None:
        self.entities_by_plugin.setdefault(entity.plugin_key, []).append(entity)
        self.entities_by_id[(entity.plugin_key, entity.entity_id)] = entity
        aliases = {entity.label, *entity.aliases}
        entity.aliases = {alias.strip() for alias in aliases if isinstance(alias, str) and alias.strip()}
        for alias in entity.aliases:
            normalized = normalize_alias(alias)
            if not normalized:
                continue
            bucket = self.alias_index.setdefault(normalized, [])
            if entity not in bucket:
                bucket.append(entity)

    def get_entities(self, plugin_key: str) -> list[CanonEntity]:
        return list(self.entities_by_plugin.get(plugin_key, []))

    def find_entity(self, reference: str, *, plugin_key: str | None = None) -> Optional[CanonEntity]:
        normalized = normalize_alias(reference)
        if not normalized:
            return None
        if plugin_key is not None:
            entity = self.entities_by_id.get((plugin_key, reference))
            if entity is not None:
                return entity
        matches = self.alias_index.get(normalized, [])
        if plugin_key is None:
            return matches[0] if matches else None
        for entity in matches:
            if entity.plugin_key == plugin_key:
                return entity
        return None

    def entity_is_mentioned(self, text: str, entity: CanonEntity) -> bool:
        for alias in sorted(entity.aliases, key=len, reverse=True):
            if len(alias) == 1 and not ASCII_TOKEN_PATTERN.fullmatch(alias):
                continue
            if content_mentions_alias(text, alias):
                return True
        return False

    def mentioned_entities(self, text: str, *, plugin_key: str | None = None) -> list[CanonEntity]:
        entities: Iterable[CanonEntity]
        if plugin_key is None:
            entities = [
                entity
                for items in self.entities_by_plugin.values()
                for entity in items
            ]
        else:
            entities = self.entities_by_plugin.get(plugin_key, [])
        seen: set[tuple[str, str]] = set()
        mentioned: list[CanonEntity] = []
        for entity in entities:
            key = (entity.plugin_key, entity.entity_id)
            if key in seen:
                continue
            if self.entity_is_mentioned(text, entity):
                mentioned.append(entity)
                seen.add(key)
        return mentioned


class CanonPlugin(Protocol):
    key: str
    entity_type: str

    def compile(self, story_bible: StoryBibleContext) -> list[CanonEntity]:
        ...

    def validate(self, snapshot: CanonSnapshot, content: str) -> list[CanonIssue]:
        ...


class CanonPluginRegistry:
    def __init__(self) -> None:
        self._plugins: list[CanonPlugin] = []

    @property
    def plugins(self) -> list[CanonPlugin]:
        return list(self._plugins)

    def register(self, plugin: CanonPlugin) -> None:
        if any(existing.key == plugin.key for existing in self._plugins):
            raise ValueError(f"Canon plugin '{plugin.key}' already registered.")
        self._plugins.append(plugin)

    def compile_snapshot(
        self,
        story_bible: StoryBibleContext,
        *,
        chapter_number: int,
        chapter_title: str | None,
    ) -> CanonSnapshot:
        snapshot = CanonSnapshot(
            story_bible=story_bible,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
        )
        for plugin in self._plugins:
            for entity in plugin.compile(story_bible):
                snapshot.add_entity(entity)
        return snapshot
