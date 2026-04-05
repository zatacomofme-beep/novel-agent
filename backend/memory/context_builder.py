from __future__ import annotations

import asyncio
from typing import Any, Optional

from memory.story_bible import StoryBibleContext
from memory.vector_store import RetrievedItem, vector_store
from memory.l2_episodic import L2EpisodicMemory, ChapterEpisode


def _episode_to_dict(episode: ChapterEpisode) -> dict[str, Any]:
    return {
        "type": "episode",
        "chapter_number": episode.chapter_number,
        "summary": episode.summary,
        "key_events": episode.key_events,
        "characters": episode.characters,
        "locations": episode.locations,
        "emotional_tone": episode.emotional_tone,
        "themes": episode.themes,
        "open_threads": episode.open_threads,
        "word_count": episode.word_count,
        "importance_score": episode.importance_score,
    }


async def build_context_bundle(
    story_bible: StoryBibleContext,
    session: "AsyncSession",
    *,
    project_id: str,
    chapter_number: int,
    chapter_title: Optional[str],
    token_budget: int = 2800,
) -> dict[str, Any]:
    query = " ".join(
        filter(
            None,
            [
                story_bible.title,
                story_bible.genre or "",
                story_bible.theme or "",
                story_bible.tone or "",
                chapter_title or "",
                f"chapter {chapter_number}",
            ],
        )
    )

    _search_tasks = []
    if story_bible.characters:
        _search_tasks.append(
            vector_store.search(
                project_id=str(story_bible.project_id),
                query=query,
                items=story_bible.characters,
                item_type="character",
                limit=5,
            )
        )
    if story_bible.world_settings:
        _search_tasks.append(
            vector_store.search(
                project_id=str(story_bible.project_id),
                query=query,
                items=story_bible.world_settings,
                item_type="world_setting",
                limit=5,
            )
        )
    if story_bible.items:
        _search_tasks.append(
            vector_store.search(
                project_id=str(story_bible.project_id),
                query=query,
                items=story_bible.items,
                item_type="item",
                limit=4,
            )
        )
    if story_bible.factions:
        _search_tasks.append(
            vector_store.search(
                project_id=str(story_bible.project_id),
                query=query,
                items=story_bible.factions,
                item_type="faction",
                limit=4,
            )
        )
    if story_bible.locations:
        _search_tasks.append(
            vector_store.search(
                project_id=str(story_bible.project_id),
                query=query,
                items=story_bible.locations,
                item_type="location",
                limit=4,
            )
        )
    if story_bible.plot_threads:
        _search_tasks.append(
            vector_store.search(
                project_id=str(story_bible.project_id),
                query=query,
                items=story_bible.plot_threads,
                item_type="plot_thread",
                limit=4,
            )
        )
    if story_bible.foreshadowing:
        _search_tasks.append(
            vector_store.search(
                project_id=str(story_bible.project_id),
                query=query,
                items=story_bible.foreshadowing,
                item_type="foreshadowing",
                limit=3,
            )
        )
    if story_bible.timeline_events:
        _search_tasks.append(
            vector_store.search(
                project_id=str(story_bible.project_id),
                query=query,
                items=story_bible.timeline_events,
                item_type="timeline_event",
                limit=3,
            )
        )

    retrieval_batches = await asyncio.gather(*_search_tasks) if _search_tasks else []
    retrieved: list[RetrievedItem] = [
        item for batch in retrieval_batches for item in batch
    ]

    l2 = L2EpisodicMemory(session)
    try:
        recent_episodes = await l2.get_recent_episodes(
            project_id=story_bible.project_id,
            before_chapter=chapter_number,
            limit=5,
        )
        episode_dicts = [_episode_to_dict(ep) for ep in recent_episodes]
    except Exception:
        episode_dicts = []

    ranked = sorted(retrieved, key=lambda item: item.score, reverse=True)
    selected_items: list[dict[str, Any]] = []
    consumed = 0
    for item in ranked:
        serialized = {
            "type": item.item_type,
            "backend": item.backend,
            "score": round(item.score, 3),
            "payload": item.payload,
        }
        estimated_cost = len(str(serialized))
        if consumed + estimated_cost > token_budget:
            continue
        selected_items.append(serialized)
        consumed += estimated_cost

    episode_budget = int(token_budget * 0.15)
    for ep_dict in episode_dicts:
        ep_size = len(str(ep_dict))
        if consumed + ep_size > token_budget:
            break
        selected_items.append(ep_dict)
        consumed += ep_size

    return {
        "query": query,
        "token_budget": token_budget,
        "estimated_usage": consumed,
        "retrieval_backends": sorted({item.backend for item in ranked}),
        "retrieved_items": selected_items,
    }
