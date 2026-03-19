from __future__ import annotations

import asyncio
from typing import Any
from typing import Optional

from memory.story_bible import StoryBibleContext
from memory.vector_store import RetrievedItem, vector_store


async def build_context_bundle(
    story_bible: StoryBibleContext,
    *,
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

    retrieval_batches = await asyncio.gather(
        vector_store.search(
            project_id=str(story_bible.project_id),
            query=query,
            items=story_bible.characters,
            item_type="character",
            limit=5,
        ),
        vector_store.search(
            project_id=str(story_bible.project_id),
            query=query,
            items=story_bible.world_settings,
            item_type="world_setting",
            limit=5,
        ),
        vector_store.search(
            project_id=str(story_bible.project_id),
            query=query,
            items=story_bible.locations,
            item_type="location",
            limit=4,
        ),
        vector_store.search(
            project_id=str(story_bible.project_id),
            query=query,
            items=story_bible.plot_threads,
            item_type="plot_thread",
            limit=4,
        ),
        vector_store.search(
            project_id=str(story_bible.project_id),
            query=query,
            items=story_bible.foreshadowing,
            item_type="foreshadowing",
            limit=3,
        ),
        vector_store.search(
            project_id=str(story_bible.project_id),
            query=query,
            items=story_bible.timeline_events,
            item_type="timeline_event",
            limit=3,
        ),
    )
    retrieved: list[RetrievedItem] = [
        item for batch in retrieval_batches for item in batch
    ]

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

    return {
        "query": query,
        "token_budget": token_budget,
        "estimated_usage": consumed,
        "retrieval_backends": sorted({item.backend for item in ranked}),
        "retrieved_items": selected_items,
    }
