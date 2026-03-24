from __future__ import annotations

from collections import Counter
import re
from typing import Any, Iterable, Optional

from canon.base import (
    CanonEntity,
    CanonIssue,
    CanonPluginRegistry,
    CanonSnapshot,
    as_dict,
    as_list,
    build_evidence_excerpt,
    clean_strings,
    content_mentions_alias,
    entity_ref,
)
from memory.story_bible import StoryBibleContext


def _boolish(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return default


def _collect_aliases(label: str, data: dict[str, Any], *extra_keys: str) -> set[str]:
    aliases = {label.strip()} if label.strip() else set()
    aliases.update(clean_strings(data.get("aliases")))
    for key in extra_keys:
        aliases.update(clean_strings(data.get(key)))
    return {item for item in aliases if len(item) > 1 or item.isascii()}


def _derive_foreshadow_aliases(content: str, data: dict[str, Any]) -> set[str]:
    aliases = set(clean_strings(data.get("aliases")))
    stripped = content.strip()
    if stripped:
        aliases.add(stripped if len(stripped) <= 24 else stripped[:24].strip())
        for delimiter in ("，", "。", "；", ",", ".", ";"):
            if delimiter in stripped:
                prefix = stripped.split(delimiter, 1)[0].strip()
                if prefix:
                    aliases.add(prefix if len(prefix) <= 24 else prefix[:24].strip())
                break
    return {item for item in aliases if item}


def _mentions_any(text: str, phrases: Iterable[str]) -> Optional[str]:
    for phrase in phrases:
        if phrase and phrase in text:
            return phrase
    return None


def _find_entity_marker_proximity(
    text: str,
    entity: CanonEntity,
    markers: Iterable[str],
    *,
    max_gap_chars: int = 6,
) -> Optional[str]:
    marker_list = [marker for marker in markers if marker]
    if not marker_list:
        return None

    marker_pattern = "|".join(re.escape(marker) for marker in marker_list)
    gap_pattern = rf'[\s"“”\'‘’]*[^\n，。！？；,.;:：]{{0,{max_gap_chars}}}[\s"“”\'‘’]*'

    for alias in sorted(entity.aliases, key=len, reverse=True):
        if len(alias) == 1 and not alias.isascii():
            continue
        alias_pattern = re.escape(alias)
        for pattern in (
            re.compile(rf"{alias_pattern}{gap_pattern}(?:{marker_pattern})", re.IGNORECASE),
            re.compile(rf"(?:{marker_pattern}){gap_pattern}{alias_pattern}", re.IGNORECASE),
        ):
            match = pattern.search(text)
            if match:
                return match.group(0)
    return None


def _issue(
    *,
    plugin_key: str,
    code: str,
    dimension: str,
    severity: str,
    blocking: bool,
    message: str,
    entities: Iterable[CanonEntity] = (),
    expected: str | None = None,
    actual: str | None = None,
    evidence_text: str | None = None,
    fix_hint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CanonIssue:
    return CanonIssue(
        plugin_key=plugin_key,
        code=code,
        dimension=dimension,
        severity=severity,
        blocking=blocking,
        message=message,
        expected=expected,
        actual=actual,
        evidence_text=evidence_text,
        fix_hint=fix_hint,
        entity_refs=[entity_ref(entity) for entity in entities],
        metadata=metadata or {},
    )


class CharacterCanonPlugin:
    key = "character"
    entity_type = "character"

    _ALIVE_STATUSES = {"alive", "active", "在世", "存活", "alive_status"}
    _DEAD_STATUSES = {"dead", "deceased", "死亡", "已死"}
    _ALIVE_CONTRADICTIONS = ("死了", "已死", "尸体", "遗体", "葬礼")
    _DEAD_ACTIVITY_MARKERS = ("走进", "站在", "开口", "说道", "抬手", "伸手")

    def compile(self, story_bible: StoryBibleContext) -> list[CanonEntity]:
        entities: list[CanonEntity] = []
        for item in story_bible.characters:
            data = as_dict(item.get("data"))
            label = str(item.get("name") or "").strip()
            if not label:
                continue
            entities.append(
                CanonEntity(
                    plugin_key=self.key,
                    entity_type=self.entity_type,
                    entity_id=str(item.get("id") or label),
                    label=label,
                    aliases=_collect_aliases(label, data, "titles", "alt_names"),
                    data={
                        "status": data.get("status"),
                        "created_chapter": item.get("created_chapter"),
                        "relationships": as_list(data.get("relationships")),
                        "items": as_list(data.get("items")),
                    },
                    source_payload=item,
                )
            )
        return entities

    def validate(self, snapshot: CanonSnapshot, content: str) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        current_chapter = snapshot.chapter_number
        for entity in snapshot.mentioned_entities(content, plugin_key=self.key):
            created_chapter = entity.data.get("created_chapter")
            if isinstance(created_chapter, int) and created_chapter > current_chapter:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="character.before_introduction",
                        dimension="canon.character_introduction",
                        severity="high",
                        blocking=True,
                        message=f"人物“{entity.label}”在第 {created_chapter} 章才应登场，但本章提前出现。",
                        entities=[entity],
                        expected=f"第 {created_chapter} 章及之后再出现该人物。",
                        actual=f"第 {current_chapter} 章正文提到了“{entity.label}”。",
                        evidence_text=build_evidence_excerpt(content, entity.label),
                        fix_hint="把该人物替换为已登场角色，或把其正式登场信息前移到 Story Bible。",
                    )
                )

            status = str(entity.data.get("status") or "").strip().lower()
            if status in self._ALIVE_STATUSES:
                contradiction = _mentions_any(content, [f"{entity.label}{marker}" for marker in self._ALIVE_CONTRADICTIONS])
                if contradiction:
                    issues.append(
                        _issue(
                            plugin_key=self.key,
                            code="character.status_contradiction",
                            dimension="canon.character_status",
                            severity="high",
                            blocking=True,
                            message=f"人物“{entity.label}”在设定中处于存活状态，但正文出现了死亡性描述。",
                            entities=[entity],
                            expected=f"“{entity.label}”仍然存活。",
                            actual=contradiction,
                            evidence_text=build_evidence_excerpt(content, contradiction),
                            fix_hint="确认这是否是误写、误传闻或回忆片段；若设定已变更，需要同步更新 Story Bible。",
                        )
                    )
            elif status in self._DEAD_STATUSES:
                contradiction = _mentions_any(content, [f"{entity.label}{marker}" for marker in self._DEAD_ACTIVITY_MARKERS])
                if contradiction:
                    issues.append(
                        _issue(
                            plugin_key=self.key,
                            code="character.dead_activity",
                            dimension="canon.character_status",
                            severity="high",
                            blocking=True,
                            message=f"人物“{entity.label}”在设定中已死亡，但正文把其写成了当前行动中的角色。",
                            entities=[entity],
                            expected=f"“{entity.label}”不应以当前行动状态直接出场。",
                            actual=contradiction,
                            evidence_text=build_evidence_excerpt(content, contradiction),
                            fix_hint="如果这是回忆、幻觉或伪死桥段，需要在正文里明确标识。",
                        )
                    )
        return issues


class RelationshipCanonPlugin:
    key = "relationship"
    entity_type = "relationship"

    _ALLY_STATES = {"ally", "allied", "friend", "trusted", "romance", "lover", "family", "友好", "信任", "同盟"}
    _HOSTILE_STATES = {"enemy", "hostile", "rival", "betrayed", "仇敌", "敌对", "宿敌"}
    _ALLY_CONTRADICTIONS = ("仇人", "死敌", "互相防备", "恨不得杀")
    _HOSTILE_CONTRADICTIONS = ("朋友", "挚友", "信任", "并肩", "恋人", "同盟")

    def compile(self, story_bible: StoryBibleContext) -> list[CanonEntity]:
        entities: list[CanonEntity] = []
        for item in story_bible.characters:
            source_name = str(item.get("name") or "").strip()
            if not source_name:
                continue
            data = as_dict(item.get("data"))
            relationships = as_list(data.get("relationships"))
            for index, relation in enumerate(relationships):
                relation_data = relation if isinstance(relation, dict) else {"target": relation}
                target_name = str(
                    relation_data.get("target")
                    or relation_data.get("character")
                    or relation_data.get("name")
                    or ""
                ).strip()
                if not target_name:
                    continue
                relation_state = str(
                    relation_data.get("status")
                    or relation_data.get("type")
                    or "related"
                ).strip()
                entities.append(
                    CanonEntity(
                        plugin_key=self.key,
                        entity_type=self.entity_type,
                        entity_id=f"{item.get('id') or source_name}:{index}",
                        label=f"{source_name}->{target_name}",
                        aliases=set(),
                        data={
                            "source_name": source_name,
                            "target_name": target_name,
                            "state": relation_state,
                            "since_chapter": relation_data.get("since_chapter"),
                        },
                        source_payload=relation_data,
                    )
                )
        return entities

    def validate(self, snapshot: CanonSnapshot, content: str) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        current_chapter = snapshot.chapter_number
        for entity in snapshot.get_entities(self.key):
            source = snapshot.find_entity(str(entity.data.get("source_name") or ""), plugin_key="character")
            target = snapshot.find_entity(str(entity.data.get("target_name") or ""), plugin_key="character")
            if source is None or target is None:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="relationship.unknown_character",
                        dimension="canon.relationship_integrity",
                        severity="medium",
                        blocking=False,
                        message=f"关系“{entity.label}”引用了不存在的人物，当前规范数据不完整。",
                        entities=[item for item in (source, target) if item is not None],
                        actual=entity.label,
                        fix_hint="在角色资料里修正 relationship.target，确保它指向已登记人物。",
                    )
                )
                continue
            since_chapter = entity.data.get("since_chapter")
            if (
                isinstance(since_chapter, int)
                and since_chapter > current_chapter
                and snapshot.entity_is_mentioned(content, source)
                and snapshot.entity_is_mentioned(content, target)
            ):
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="relationship.before_established",
                        dimension="canon.relationship_timing",
                        severity="medium",
                        blocking=False,
                        message=f"“{source.label}”与“{target.label}”的关系按设定应在第 {since_chapter} 章后才成立。",
                        entities=[source, target],
                        expected=f"第 {since_chapter} 章后再显式建立这层关系。",
                        actual=f"第 {current_chapter} 章正文已同时推进这对关系。",
                        fix_hint="弱化关系定性，或把设定里的建立章节前移。",
                    )
                )

            if not (snapshot.entity_is_mentioned(content, source) and snapshot.entity_is_mentioned(content, target)):
                continue

            relation_state = str(entity.data.get("state") or "").strip().lower()
            if relation_state in self._ALLY_STATES:
                contradiction = _mentions_any(content, self._ALLY_CONTRADICTIONS)
                if contradiction:
                    issues.append(
                        _issue(
                            plugin_key=self.key,
                            code="relationship.state_contradiction",
                            dimension="canon.relationship_state",
                            severity="high",
                            blocking=True,
                            message=f"“{source.label}”与“{target.label}”当前关系更偏友方，但正文写出了明显敌对信号。",
                            entities=[source, target],
                            expected=f"{source.label} 与 {target.label} 应维持友方/信任关系。",
                            actual=contradiction,
                            evidence_text=build_evidence_excerpt(content, contradiction),
                            fix_hint="确认这是关系正式破裂，还是当前场景的情绪性冲突；如为前者，需同步更新关系设定。",
                        )
                    )
            elif relation_state in self._HOSTILE_STATES:
                contradiction = _mentions_any(content, self._HOSTILE_CONTRADICTIONS)
                if contradiction:
                    issues.append(
                        _issue(
                            plugin_key=self.key,
                            code="relationship.state_contradiction",
                            dimension="canon.relationship_state",
                            severity="high",
                            blocking=True,
                            message=f"“{source.label}”与“{target.label}”当前关系应偏敌对，但正文给出了过强的亲密/信任信号。",
                            entities=[source, target],
                            expected=f"{source.label} 与 {target.label} 仍处于敌对或互不信任状态。",
                            actual=contradiction,
                            evidence_text=build_evidence_excerpt(content, contradiction),
                            fix_hint="若关系确实发生转折，请在本章中补足转折原因，并同步更新 Story Bible。",
                        )
                    )
        return issues

    def validate_snapshot(self, snapshot: CanonSnapshot) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        for entity in snapshot.get_entities(self.key):
            source_name = str(entity.data.get("source_name") or "").strip()
            target_name = str(entity.data.get("target_name") or "").strip()
            source = snapshot.find_entity(source_name, plugin_key="character")
            target = snapshot.find_entity(target_name, plugin_key="character")

            if source is None or target is None:
                missing = [name for name, ref in ((source_name, source), (target_name, target)) if name and ref is None]
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="relationship.unknown_character",
                        dimension="canon.relationship_integrity",
                        severity="high",
                        blocking=True,
                        message=f"关系“{entity.label}”引用了未登记人物，当前 Story Bible 关系图不自洽。",
                        entities=[item for item in (source, target) if item is not None],
                        expected="relationship.target 应指向已登记人物。",
                        actual="、".join(missing) if missing else entity.label,
                        fix_hint="在角色资料里修正 relationships，确保 source/target 都能解析到真实人物。",
                    )
                )
                continue

            since_chapter = entity.data.get("since_chapter")
            source_created_chapter = source.data.get("created_chapter")
            target_created_chapter = target.data.get("created_chapter")
            required_floor = max(
                value
                for value in (source_created_chapter, target_created_chapter)
                if isinstance(value, int)
            ) if any(isinstance(value, int) for value in (source_created_chapter, target_created_chapter)) else None
            if (
                isinstance(since_chapter, int)
                and required_floor is not None
                and since_chapter < required_floor
            ):
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="relationship.invalid_since_chapter",
                        dimension="canon.relationship_timing",
                        severity="medium",
                        blocking=False,
                        message=(
                            f"关系“{entity.label}”的建立章节早于相关人物的正式登场章节，"
                            "当前 Story Bible 时序存在前置冲突。"
                        ),
                        entities=[source, target],
                        expected=f"since_chapter 不早于第 {required_floor} 章。",
                        actual=f"当前 since_chapter={since_chapter}。",
                        fix_hint="把关系建立章节后移，或同步调整相关人物的首次登场章节。",
                    )
                )
        return issues


class ItemCanonPlugin:
    key = "item"
    entity_type = "item"

    _UNUSABLE_STATES = {"destroyed", "lost", "broken", "封印", "毁坏", "遗失"}
    _ACTIVE_USE_MARKERS = ("拿起", "握住", "挥动", "启动", "佩戴", "使用")

    def compile(self, story_bible: StoryBibleContext) -> list[CanonEntity]:
        entities: list[CanonEntity] = []
        for item in _story_bible_item_entries(story_bible):
            name = str(item.get("name") or item.get("title") or "").strip()
            if not name:
                continue
            entities.append(
                CanonEntity(
                    plugin_key=self.key,
                    entity_type=self.entity_type,
                    entity_id=str(item.get("id") or item.get("key") or name),
                    label=name,
                    aliases=_collect_aliases(name, item),
                    data={
                        "status": item.get("status"),
                        "owner": item.get("owner"),
                        "location": item.get("location"),
                        "introduced_chapter": item.get("introduced_chapter"),
                        "forbidden_holders": clean_strings(item.get("forbidden_holders")),
                    },
                    source_payload=item,
                )
            )
        return entities

    def validate(self, snapshot: CanonSnapshot, content: str) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        current_chapter = snapshot.chapter_number
        for entity in snapshot.mentioned_entities(content, plugin_key=self.key):
            introduced_chapter = entity.data.get("introduced_chapter")
            if isinstance(introduced_chapter, int) and introduced_chapter > current_chapter:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="item.before_introduction",
                        dimension="canon.item_introduction",
                        severity="high",
                        blocking=True,
                        message=f"物品“{entity.label}”设定为第 {introduced_chapter} 章后才出现，但本章提前使用。",
                        entities=[entity],
                        expected=f"第 {introduced_chapter} 章及之后再出现该物品。",
                        actual=f"第 {current_chapter} 章提到了“{entity.label}”。",
                        evidence_text=build_evidence_excerpt(content, entity.label),
                        fix_hint="改用已出现物品，或把该物品的引入时间前移。",
                    )
                )

            item_status = str(entity.data.get("status") or "").strip().lower()
            if item_status in self._UNUSABLE_STATES:
                contradiction = _find_entity_marker_proximity(
                    content,
                    entity,
                    self._ACTIVE_USE_MARKERS,
                )
                if contradiction:
                    issues.append(
                        _issue(
                            plugin_key=self.key,
                            code="item.unusable_state",
                            dimension="canon.item_state",
                            severity="high",
                            blocking=True,
                            message=f"物品“{entity.label}”当前被标记为不可用，但正文仍把它写成可直接操作的物品。",
                            entities=[entity],
                            expected=f"“{entity.label}”不应处于可直接使用状态。",
                            actual=contradiction,
                            evidence_text=build_evidence_excerpt(content, contradiction),
                            fix_hint="确认这是新修复/替代物，还是正文误用了旧状态。",
                        )
                    )

            for holder_name in entity.data.get("forbidden_holders", []):
                holder = snapshot.find_entity(holder_name, plugin_key="character")
                if holder is None:
                    continue
                if snapshot.entity_is_mentioned(content, holder):
                    issues.append(
                        _issue(
                            plugin_key=self.key,
                            code="item.forbidden_holder",
                            dimension="canon.item_ownership",
                            severity="medium",
                            blocking=False,
                            message=f"物品“{entity.label}”被设定为不应落到“{holder.label}”手中，但本章把两者放在了同一场景。",
                            entities=[entity, holder],
                            actual=f"{holder.label} 与 {entity.label} 同章出现。",
                            evidence_text=build_evidence_excerpt(content, entity.label),
                            fix_hint="如果发生了归属转移，需要把转移动作写清并更新物品设定。",
                        )
                    )
        return issues

    def validate_snapshot(self, snapshot: CanonSnapshot) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        for entity in snapshot.get_entities(self.key):
            owner_name = str(entity.data.get("owner") or "").strip()
            if owner_name and snapshot.find_entity(owner_name, plugin_key="character") is None:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="item.unknown_owner",
                        dimension="canon.item_ownership",
                        severity="high",
                        blocking=True,
                        message=f"物品“{entity.label}”指向了不存在的持有者，当前 Story Bible 物品归属链断裂。",
                        entities=[entity],
                        expected="owner 指向已登记人物。",
                        actual=owner_name,
                        fix_hint="修正 owner，或先在人物档案中补齐对应角色。",
                    )
                )

            location_name = str(entity.data.get("location") or "").strip()
            if location_name and snapshot.find_entity(location_name, plugin_key="location") is None:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="item.unknown_location",
                        dimension="canon.item_location",
                        severity="medium",
                        blocking=False,
                        message=f"物品“{entity.label}”指向了不存在的地点，当前 Story Bible 空间锚点不完整。",
                        entities=[entity],
                        expected="location 指向已登记地点。",
                        actual=location_name,
                        fix_hint="修正 location，或在地点分区补齐对应地点。",
                    )
                )

            for holder_name in entity.data.get("forbidden_holders", []):
                if snapshot.find_entity(holder_name, plugin_key="character") is None:
                    issues.append(
                        _issue(
                            plugin_key=self.key,
                            code="item.unknown_forbidden_holder",
                            dimension="canon.item_ownership",
                            severity="medium",
                            blocking=False,
                            message=f"物品“{entity.label}”的禁持有人列表包含未登记人物，约束数据本身不完整。",
                            entities=[entity],
                            expected="forbidden_holders 只包含已登记人物。",
                            actual=holder_name,
                            fix_hint="删除无效名字，或先补齐对应角色档案。",
                        )
                    )
        return issues


class FactionCanonPlugin:
    key = "faction"
    entity_type = "faction"

    def compile(self, story_bible: StoryBibleContext) -> list[CanonEntity]:
        entities: list[CanonEntity] = []
        for item in _story_bible_faction_entries(story_bible):
            name = str(item.get("name") or item.get("title") or item.get("key") or "").strip()
            if not name:
                continue
            entities.append(
                CanonEntity(
                    plugin_key=self.key,
                    entity_type=self.entity_type,
                    entity_id=str(item.get("id") or item.get("key") or name),
                    label=name,
                    aliases=_collect_aliases(name, item),
                    data={
                        "leader": item.get("leader"),
                        "members": clean_strings(item.get("members")),
                        "territory": item.get("territory"),
                        "resources": clean_strings(item.get("resources")),
                        "ideology": item.get("ideology"),
                    },
                    source_payload=item,
                )
            )
        return entities

    def validate(self, snapshot: CanonSnapshot, content: str) -> list[CanonIssue]:
        return []

    def validate_snapshot(self, snapshot: CanonSnapshot) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        for entity in snapshot.get_entities(self.key):
            leader_name = str(entity.data.get("leader") or "").strip()
            if leader_name and snapshot.find_entity(leader_name, plugin_key="character") is None:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="faction.unknown_leader",
                        dimension="canon.faction_integrity",
                        severity="high",
                        blocking=True,
                        message=f"势力“{entity.label}”指向了不存在的首领，当前 Story Bible 势力链断裂。",
                        entities=[entity],
                        expected="leader 指向已登记人物。",
                        actual=leader_name,
                        fix_hint="修正 leader，或先在人物分区补齐对应角色。",
                    )
                )

            territory_name = str(entity.data.get("territory") or "").strip()
            if territory_name and snapshot.find_entity(territory_name, plugin_key="location") is None:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="faction.unknown_territory",
                        dimension="canon.faction_territory",
                        severity="medium",
                        blocking=False,
                        message=f"势力“{entity.label}”指向了不存在的势力范围，当前 Story Bible 空间锚点不完整。",
                        entities=[entity],
                        expected="territory 指向已登记地点。",
                        actual=territory_name,
                        fix_hint="修正 territory，或在地点分区补齐对应地点。",
                    )
                )

            for member_name in entity.data.get("members", []):
                if snapshot.find_entity(member_name, plugin_key="character") is None:
                    issues.append(
                        _issue(
                            plugin_key=self.key,
                            code="faction.unknown_member",
                            dimension="canon.faction_integrity",
                            severity="medium",
                            blocking=False,
                            message=f"势力“{entity.label}”的成员列表包含未登记人物，当前势力关系数据不完整。",
                            entities=[entity],
                            expected="members 只包含已登记人物。",
                            actual=member_name,
                            fix_hint="删除无效成员名，或先补齐对应角色档案。",
                        )
                    )
        return issues


class LocationCanonPlugin:
    key = "location"
    entity_type = "location"

    def compile(self, story_bible: StoryBibleContext) -> list[CanonEntity]:
        entities: list[CanonEntity] = []
        for item in story_bible.locations:
            data = as_dict(item.get("data"))
            label = str(item.get("name") or "").strip()
            if not label:
                continue
            entities.append(
                CanonEntity(
                    plugin_key=self.key,
                    entity_type=self.entity_type,
                    entity_id=str(item.get("id") or label),
                    label=label,
                    aliases=_collect_aliases(label, data),
                    data={
                        "introduced_chapter": data.get("introduced_chapter"),
                        "required_keywords": clean_strings(data.get("required_keywords")),
                        "forbidden_keywords": clean_strings(data.get("forbidden_keywords")),
                    },
                    source_payload=item,
                )
            )
        return entities

    def validate(self, snapshot: CanonSnapshot, content: str) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        current_chapter = snapshot.chapter_number
        for entity in snapshot.mentioned_entities(content, plugin_key=self.key):
            introduced_chapter = entity.data.get("introduced_chapter")
            if isinstance(introduced_chapter, int) and introduced_chapter > current_chapter:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="location.before_introduction",
                        dimension="canon.location_introduction",
                        severity="high",
                        blocking=True,
                        message=f"地点“{entity.label}”设定为第 {introduced_chapter} 章后才正式出现，但本章提前写入。",
                        entities=[entity],
                        fix_hint="确认这是不是同地点的未命名预告场景；否则应调整地点引入顺序。",
                    )
                )

            forbidden = _mentions_any(content, entity.data.get("forbidden_keywords", []))
            if forbidden:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="location.forbidden_anchor",
                        dimension="canon.location_anchor",
                        severity="medium",
                        blocking=False,
                        message=f"地点“{entity.label}”的场景描写碰到了已标记的禁用锚点。",
                        entities=[entity],
                        actual=forbidden,
                        evidence_text=build_evidence_excerpt(content, forbidden),
                        fix_hint="检查这是不是设定冲突，或仅需把环境细节改成该地点允许的样子。",
                    )
                )

            required_keywords = entity.data.get("required_keywords", [])
            if required_keywords and not any(keyword in content for keyword in required_keywords):
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="location.anchor_missing",
                        dimension="canon.location_anchor",
                        severity="low",
                        blocking=False,
                        message=f"地点“{entity.label}”已在正文出现，但缺少设定中常用的场景锚点。",
                        entities=[entity],
                        expected=f"至少出现这些锚点之一：{', '.join(required_keywords[:4])}",
                        actual=f"正文提到“{entity.label}”但没有带出典型环境标记。",
                        fix_hint="补一两处地点特征，能显著降低世界连续性的漂移感。",
                    )
                )
        return issues


class WorldRuleCanonPlugin:
    key = "world_rule"
    entity_type = "world_rule"

    def compile(self, story_bible: StoryBibleContext) -> list[CanonEntity]:
        entities: list[CanonEntity] = []
        for item in story_bible.world_settings:
            data = as_dict(item.get("data"))
            label = str(item.get("title") or item.get("key") or "").strip()
            if not label:
                continue
            entities.append(
                CanonEntity(
                    plugin_key=self.key,
                    entity_type=self.entity_type,
                    entity_id=str(item.get("id") or item.get("key") or label),
                    label=label,
                    aliases=_collect_aliases(label, data, "keys"),
                    data={
                        "required_keywords": clean_strings(data.get("required_keywords")),
                        "contradiction_keywords": clean_strings(data.get("contradiction_keywords"))
                        or clean_strings(data.get("forbidden_keywords")),
                        "applies_globally": _boolish(data.get("applies_globally"), default=True),
                    },
                    source_payload=item,
                )
            )
        return entities

    def validate(self, snapshot: CanonSnapshot, content: str) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        for entity in snapshot.get_entities(self.key):
            contradiction = _mentions_any(content, entity.data.get("contradiction_keywords", []))
            if contradiction is not None and (
                entity.data.get("applies_globally") or snapshot.entity_is_mentioned(content, entity)
            ):
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="world_rule.contradiction",
                        dimension="canon.world_rule",
                        severity="high",
                        blocking=True,
                        message=f"世界规则“{entity.label}”被正文中的描述直接冲撞。",
                        entities=[entity],
                        actual=contradiction,
                        evidence_text=build_evidence_excerpt(content, contradiction),
                        fix_hint="如果这是规则被打破的关键情节，需要把破例条件写清；否则应回退到既有世界规则。",
                    )
                )
        return issues


class TimelineCanonPlugin:
    key = "timeline"
    entity_type = "timeline_event"

    def compile(self, story_bible: StoryBibleContext) -> list[CanonEntity]:
        entities: list[CanonEntity] = []
        for item in story_bible.timeline_events:
            data = as_dict(item.get("data"))
            label = str(item.get("title") or "").strip()
            if not label:
                continue
            entities.append(
                CanonEntity(
                    plugin_key=self.key,
                    entity_type=self.entity_type,
                    entity_id=str(item.get("id") or label),
                    label=label,
                    aliases=_collect_aliases(label, data),
                    data={
                        "chapter_number": item.get("chapter_number"),
                    },
                    source_payload=item,
                )
            )
        return entities

    def validate(self, snapshot: CanonSnapshot, content: str) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        current_chapter = snapshot.chapter_number
        for entity in snapshot.mentioned_entities(content, plugin_key=self.key):
            event_chapter = entity.data.get("chapter_number")
            if isinstance(event_chapter, int) and event_chapter > current_chapter:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="timeline.future_event",
                        dimension="canon.timeline_order",
                        severity="high",
                        blocking=True,
                        message=f"时间线事件“{entity.label}”被安排在第 {event_chapter} 章，但本章提前引用了它。",
                        entities=[entity],
                        expected=f"第 {event_chapter} 章及之后再明确提到该事件。",
                        actual=f"第 {current_chapter} 章已经出现该事件名。",
                        evidence_text=build_evidence_excerpt(content, entity.label),
                        fix_hint="如果只是预感/传闻，请在正文里明确它并非既成事实。",
                    )
                )
        return issues


class ForeshadowCanonPlugin:
    key = "foreshadow"
    entity_type = "foreshadow"

    _OPEN_STATUSES = {"pending", "planned", "planted", "active"}

    def compile(self, story_bible: StoryBibleContext) -> list[CanonEntity]:
        entities: list[CanonEntity] = []
        for item in story_bible.foreshadowing:
            label = str(item.get("content") or "").strip()
            if not label:
                continue
            data = as_dict(item)
            aliases = _derive_foreshadow_aliases(label, data)
            entities.append(
                CanonEntity(
                    plugin_key=self.key,
                    entity_type=self.entity_type,
                    entity_id=str(item.get("id") or label),
                    label=label if len(label) <= 24 else f"{label[:24]}...",
                    aliases=aliases,
                    data={
                        "raw_content": label,
                        "planted_chapter": item.get("planted_chapter"),
                        "payoff_chapter": item.get("payoff_chapter"),
                        "status": item.get("status"),
                    },
                    source_payload=item,
                )
            )
        return entities

    def validate(self, snapshot: CanonSnapshot, content: str) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        current_chapter = snapshot.chapter_number
        for entity in snapshot.get_entities(self.key):
            mentioned = snapshot.entity_is_mentioned(content, entity)
            planted_chapter = entity.data.get("planted_chapter")
            payoff_chapter = entity.data.get("payoff_chapter")
            status = str(entity.data.get("status") or "").strip().lower()

            if mentioned and isinstance(planted_chapter, int) and planted_chapter > current_chapter:
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="foreshadow.before_planting",
                        dimension="canon.foreshadow_timing",
                        severity="high",
                        blocking=True,
                        message=f"伏笔“{entity.label}”按设定要到第 {planted_chapter} 章才埋下，但本章已经提前出现。",
                        entities=[entity],
                        evidence_text=build_evidence_excerpt(content, next(iter(entity.aliases), entity.label)),
                        fix_hint="要么改成本章先埋下伏笔，要么把正文里的提前提示删除。",
                    )
                )

            if (
                isinstance(payoff_chapter, int)
                and current_chapter > payoff_chapter
                and status in self._OPEN_STATUSES
            ):
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="foreshadow.overdue",
                        dimension="canon.foreshadow_timing",
                        severity="low",
                        blocking=False,
                        message=f"伏笔“{entity.label}”按设定应在第 {payoff_chapter} 章前后兑现，但目前仍处于未收束状态。",
                        entities=[entity],
                        expected=f"到第 {payoff_chapter} 章左右给出兑现或明确延期理由。",
                        actual="当前规范数据仍标记为未完成。",
                        fix_hint="检查本章是否该承担兑现责任，或把 payoff_chapter 调整到新的计划节点。",
                    )
                )
        return issues

    def validate_snapshot(self, snapshot: CanonSnapshot) -> list[CanonIssue]:
        issues: list[CanonIssue] = []
        for entity in snapshot.get_entities(self.key):
            planted_chapter = entity.data.get("planted_chapter")
            payoff_chapter = entity.data.get("payoff_chapter")
            if (
                isinstance(planted_chapter, int)
                and isinstance(payoff_chapter, int)
                and payoff_chapter < planted_chapter
            ):
                issues.append(
                    _issue(
                        plugin_key=self.key,
                        code="foreshadow.invalid_payoff_order",
                        dimension="canon.foreshadow_timing",
                        severity="high",
                        blocking=True,
                        message=f"伏笔“{entity.label}”的兑现章节早于埋设章节，当前 Story Bible 时序自相矛盾。",
                        entities=[entity],
                        expected=f"payoff_chapter >= planted_chapter ({planted_chapter})。",
                        actual=f"当前 payoff_chapter={payoff_chapter}。",
                        fix_hint="调整 planted/payoff 章节顺序，确保伏笔链条在时间线上成立。",
                    )
                )
        return issues


def _story_bible_item_entries(story_bible: StoryBibleContext) -> list[dict[str, Any]]:
    direct_entries = [item for item in story_bible.items if isinstance(item, dict)]
    if direct_entries:
        return direct_entries

    entries: list[dict[str, Any]] = []
    for container in [*story_bible.characters, *story_bible.locations, *story_bible.world_settings]:
        data = as_dict(container.get("data"))
        for index, raw_item in enumerate(as_list(data.get("items"))):
            item_data = raw_item if isinstance(raw_item, dict) else {"name": raw_item}
            entries.append(
                {
                    "id": f"{container.get('id') or container.get('name') or container.get('title') or index}:item:{index}",
                    "key": item_data.get("key"),
                    "name": item_data.get("name") or item_data.get("title"),
                    "status": item_data.get("status"),
                    "owner": item_data.get("owner") or container.get("name"),
                    "location": item_data.get("location"),
                    "introduced_chapter": item_data.get("introduced_chapter"),
                    "forbidden_holders": item_data.get("forbidden_holders"),
                    "aliases": item_data.get("aliases"),
                }
            )
    return entries


def _story_bible_faction_entries(story_bible: StoryBibleContext) -> list[dict[str, Any]]:
    direct_entries = [item for item in story_bible.factions if isinstance(item, dict)]
    if direct_entries:
        return direct_entries

    entries: list[dict[str, Any]] = []
    for world_setting in story_bible.world_settings:
        data = as_dict(world_setting.get("data"))
        if str(data.get("entity_type") or "").strip().lower() != "faction":
            continue
        entries.append(
            {
                "id": world_setting.get("id"),
                "key": world_setting.get("key"),
                "name": data.get("name") or world_setting.get("title") or world_setting.get("key"),
                "leader": data.get("leader"),
                "members": data.get("members"),
                "territory": data.get("territory"),
                "resources": data.get("resources"),
                "ideology": data.get("ideology"),
                "aliases": data.get("aliases"),
            }
        )
    return entries


canon_plugin_registry = CanonPluginRegistry()
canon_plugin_registry.register(CharacterCanonPlugin())
canon_plugin_registry.register(RelationshipCanonPlugin())
canon_plugin_registry.register(ItemCanonPlugin())
canon_plugin_registry.register(FactionCanonPlugin())
canon_plugin_registry.register(LocationCanonPlugin())
canon_plugin_registry.register(WorldRuleCanonPlugin())
canon_plugin_registry.register(TimelineCanonPlugin())
canon_plugin_registry.register(ForeshadowCanonPlugin())
