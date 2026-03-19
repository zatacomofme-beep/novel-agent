from __future__ import annotations

import unittest

from memory.vector_store import HybridVectorStore, RetrievedItem


class VectorStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_falls_back_to_lexical_when_qdrant_is_unavailable(self) -> None:
        store = HybridVectorStore()
        store._qdrant_import_error = True

        results = await store.search(
            project_id="project-1",
            query="Lin Harbor",
            items=[
                {
                    "id": "character-1",
                    "name": "Lin",
                    "data": {"home": "Harbor"},
                }
            ],
            item_type="character",
            limit=5,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].backend, "lexical")
        self.assertEqual(results[0].item_id, "character-1")

    def test_merge_results_marks_hybrid_when_same_item_matches_twice(self) -> None:
        store = HybridVectorStore()

        merged = store._merge_results(
            qdrant_results=[
                RetrievedItem(
                    item_type="character",
                    item_id="character-1",
                    score=0.91,
                    payload={"name": "Lin"},
                    backend="qdrant",
                )
            ],
            lexical_results=[
                RetrievedItem(
                    item_type="character",
                    item_id="character-1",
                    score=0.53,
                    payload={"name": "Lin"},
                    backend="lexical",
                )
            ],
            limit=5,
        )

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].backend, "hybrid")
        self.assertEqual(merged[0].score, 0.91)
