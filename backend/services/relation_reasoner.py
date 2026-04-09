from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InferredRelation:
    from_entity: str
    to_entity: str
    inferred_relation: str
    confidence: float
    path: list[dict[str, Any]] = field(default_factory=list)


_FAMILY_RELATIONS = {
    "父亲", "母亲", "儿子", "女儿", "兄弟", "姐妹",
    "祖父", "祖母", "外公", "外婆", "叔叔", "阿姨",
    "丈夫", "妻子", "配偶",
}

_MENTOR_RELATIONS = {
    "师父", "师傅", "师傅", "徒弟", "师尊", "师伯", "师叔",
    "师姐", "师妹", "师兄", "师弟", "同门",
}

_FACTION_RELATIONS = {
    "盟友", "敌人", "对手", "同伙", "部下", "上司", "首领",
    "成员", "隶属",
}

_INVERSE_MAP: dict[str, str] = {
    "父亲": "子女", "母亲": "子女",
    "儿子": "父母", "女儿": "父母",
    "丈夫": "妻子", "妻子": "丈夫", "配偶": "配偶",
    "师父": "徒弟", "师傅": "徒弟", "师尊": "徒弟",
    "徒弟": "师父", "师伯": "师侄", "师叔": "师侄",
    "师姐": "师弟/师妹", "师妹": "师姐/师兄",
    "师兄": "师弟/师妹", "师弟": "师姐/师兄",
    "同门": "同门",
    "盟友": "盟友", "敌人": "敌人", "对手": "对手",
    "部下": "上司", "上司": "部下", "首领": "成员", "成员": "首领",
    "隶属": "统领", "统领": "隶属",
}


def reason_from_paths(
    paths: list[dict[str, Any]],
) -> list[InferredRelation]:
    inferred: list[InferredRelation] = []
    seen: set[str] = set()

    for path_data in paths:
        nodes = path_data.get("nodes", [])
        rel_types = path_data.get("relation_types", [])
        hops = path_data.get("hops", 0)

        if hops < 2 or len(nodes) < 3:
            continue

        start_name = nodes[0].get("name", "")
        end_name = nodes[-1].get("name", "")
        if not start_name or not end_name:
            continue

        dedup_key = f"{start_name}->{end_name}"
        if dedup_key in seen:
            continue

        result = _reason_two_hop(
            start_name=start_name,
            mid_name=nodes[1].get("name", ""),
            end_name=end_name,
            rel1=rel_types[0] if rel_types else "",
            rel2=rel_types[1] if len(rel_types) > 1 else "",
        )
        if result:
            seen.add(dedup_key)
            result.path = path_data.get("nodes", [])
            inferred.append(result)

    return inferred


def reason_from_direct_relations(
    relations: list[dict[str, Any]],
) -> list[InferredRelation]:
    inferred: list[InferredRelation] = []
    seen: set[str] = set()

    for rel in relations:
        from_name = rel.get("from", "")
        to_name = rel.get("to", "")
        relation = rel.get("relation", "")

        if not from_name or not to_name or not relation:
            continue

        inverse = _INVERSE_MAP.get(relation)
        if inverse:
            dedup_key = f"{to_name}->{from_name}:{inverse}"
            if dedup_key not in seen:
                seen.add(dedup_key)
                inferred.append(InferredRelation(
                    from_entity=to_name,
                    to_entity=from_name,
                    inferred_relation=inverse,
                    confidence=0.85,
                    path=[rel],
                ))

        if relation in _FAMILY_RELATIONS:
            dedup_key = f"{from_name}->{to_name}:family"
            if dedup_key not in seen:
                seen.add(dedup_key)
                inferred.append(InferredRelation(
                    from_entity=from_name,
                    to_entity=to_name,
                    inferred_relation=f"家族关系（{relation}）",
                    confidence=0.9,
                    path=[rel],
                ))

        if relation in _MENTOR_RELATIONS:
            dedup_key = f"{from_name}->{to_name}:mentor"
            if dedup_key not in seen:
                seen.add(dedup_key)
                inferred.append(InferredRelation(
                    from_entity=from_name,
                    to_entity=to_name,
                    inferred_relation=f"师门关系（{relation}）",
                    confidence=0.9,
                    path=[rel],
                ))

        if relation in _FACTION_RELATIONS:
            dedup_key = f"{from_name}->{to_name}:faction"
            if dedup_key not in seen:
                seen.add(dedup_key)
                inferred.append(InferredRelation(
                    from_entity=from_name,
                    to_entity=to_name,
                    inferred_relation=f"阵营关系（{relation}）",
                    confidence=0.85,
                    path=[rel],
                ))

    return inferred


def _reason_two_hop(
    start_name: str,
    mid_name: str,
    end_name: str,
    rel1: str,
    rel2: str,
) -> InferredRelation | None:
    if rel1 in _FAMILY_RELATIONS and rel2 in _FAMILY_RELATIONS:
        return InferredRelation(
            from_entity=start_name,
            to_entity=end_name,
            inferred_relation=f"家族关系（经{mid_name}：{rel1}→{rel2}）",
            confidence=0.75,
        )

    if rel1 in _MENTOR_RELATIONS and rel2 in _MENTOR_RELATIONS:
        return InferredRelation(
            from_entity=start_name,
            to_entity=end_name,
            inferred_relation=f"同门关系（经{mid_name}：{rel1}→{rel2}）",
            confidence=0.8,
        )

    if rel1 in _FAMILY_RELATIONS and rel2 in _MENTOR_RELATIONS:
        return InferredRelation(
            from_entity=start_name,
            to_entity=end_name,
            inferred_relation=f"家族与师门交叉关系（经{mid_name}：{rel1}→{rel2}）",
            confidence=0.7,
        )

    if rel1 in _MENTOR_RELATIONS and rel2 in _FAMILY_RELATIONS:
        return InferredRelation(
            from_entity=start_name,
            to_entity=end_name,
            inferred_relation=f"师门与家族交叉关系（经{mid_name}：{rel1}→{rel2}）",
            confidence=0.7,
        )

    if (rel1 in _FACTION_RELATIONS or rel1 == "盟友") and rel2 in _FACTION_RELATIONS:
        return InferredRelation(
            from_entity=start_name,
            to_entity=end_name,
            inferred_relation=f"阵营关联（经{mid_name}：{rel1}→{rel2}）",
            confidence=0.65,
        )

    if (rel1 in _FACTION_RELATIONS or rel1 == "敌人") and rel2 in _FACTION_RELATIONS:
        return InferredRelation(
            from_entity=start_name,
            to_entity=end_name,
            inferred_relation=f"敌对阵营关联（经{mid_name}：{rel1}→{rel2}）",
            confidence=0.6,
        )

    return None


def format_inferred_relations_for_constraints(
    inferred: list[InferredRelation],
    max_count: int = 10,
) -> list[str]:
    lines: list[str] = []
    sorted_inferred = sorted(inferred, key=lambda x: x.confidence, reverse=True)
    for item in sorted_inferred[:max_count]:
        lines.append(
            f"角色「{item.from_entity}」与「{item.to_entity}」存在{item.inferred_relation}"
        )
    return lines
