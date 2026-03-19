from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any

from core.config import get_settings


TOKEN_PATTERN = re.compile(r"[\w\u4e00-\u9fff]+")


def tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_PATTERN.findall(text)}


@dataclass
class RetrievedItem:
    item_type: str
    item_id: str
    score: float
    payload: dict[str, Any]
    backend: str


class LexicalVectorStore:
    def search(
        self,
        *,
        query: str,
        items: list[dict[str, Any]],
        item_type: str,
        limit: int = 5,
    ) -> list[RetrievedItem]:
        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        results: list[RetrievedItem] = []
        for item in items:
            searchable = " ".join(
                str(value)
                for key, value in item.items()
                if key not in {"id"} and value is not None
            )
            item_tokens = tokenize(searchable)
            if not item_tokens:
                continue

            overlap = query_tokens & item_tokens
            if not overlap:
                continue

            score = len(overlap) / max(1, len(query_tokens))
            results.append(
                RetrievedItem(
                    item_type=item_type,
                    item_id=str(item.get("id", "")),
                    score=score,
                    payload=item,
                    backend="lexical",
                )
            )

        return sorted(results, key=lambda item: item.score, reverse=True)[:limit]


class HybridVectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.lexical = LexicalVectorStore()
        self.qdrant_url = settings.qdrant_url
        self.collection_prefix = settings.qdrant_collection_prefix
        self.request_timeout_seconds = settings.qdrant_request_timeout_seconds
        self.embedding_dimensions = settings.vector_embedding_dimensions
        self._client = None
        self._indexed_hashes: dict[str, str] = {}
        self._qdrant_import_error = False

    async def search(
        self,
        *,
        project_id: str,
        query: str,
        items: list[dict[str, Any]],
        item_type: str,
        limit: int = 5,
    ) -> list[RetrievedItem]:
        lexical_results = self.lexical.search(
            query=query,
            items=items,
            item_type=item_type,
            limit=limit,
        )
        qdrant_results = await self._search_qdrant(
            project_id=project_id,
            query=query,
            items=items,
            item_type=item_type,
            limit=limit,
        )
        if not qdrant_results:
            return lexical_results
        return self._merge_results(qdrant_results, lexical_results, limit)

    async def _search_qdrant(
        self,
        *,
        project_id: str,
        query: str,
        items: list[dict[str, Any]],
        item_type: str,
        limit: int,
    ) -> list[RetrievedItem]:
        if not items or not tokenize(query):
            return []

        client = await self._get_client()
        if client is None:
            return []

        dataset_hash = self._dataset_hash(items)
        collection_name = self._collection_name(project_id, item_type)
        try:
            await self._ensure_collection(client, collection_name)
            if self._indexed_hashes.get(collection_name) != dataset_hash:
                await client.upsert(
                    collection_name=collection_name,
                    wait=True,
                    points=self._build_points(items, dataset_hash),
                )
                self._indexed_hashes[collection_name] = dataset_hash

            search_result = await client.search(
                collection_name=collection_name,
                query_vector=self._embed_text(query),
                query_filter=self._build_dataset_filter(dataset_hash),
                limit=limit,
                with_payload=True,
            )
        except Exception:
            return []

        results: list[RetrievedItem] = []
        for hit in search_result:
            payload = getattr(hit, "payload", None) or {}
            source_payload = payload.get("source_payload")
            if not isinstance(source_payload, dict):
                continue
            results.append(
                RetrievedItem(
                    item_type=item_type,
                    item_id=str(payload.get("source_id", "")),
                    score=self._normalize_qdrant_score(float(getattr(hit, "score", 0.0))),
                    payload=source_payload,
                    backend="qdrant",
                )
            )
        return results

    async def _get_client(self):
        if self._qdrant_import_error:
            return None
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import AsyncQdrantClient
        except ImportError:
            self._qdrant_import_error = True
            return None

        self._client = AsyncQdrantClient(
            url=self.qdrant_url,
            timeout=self.request_timeout_seconds,
        )
        return self._client

    async def _ensure_collection(self, client, collection_name: str) -> None:
        if await client.collection_exists(collection_name):
            return

        models = self._models()
        await client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=self.embedding_dimensions,
                distance=models.Distance.COSINE,
            ),
        )

    def _build_points(self, items: list[dict[str, Any]], dataset_hash: str):
        models = self._models()
        points = []
        for item in items:
            item_id = self._source_item_id(item)
            points.append(
                models.PointStruct(
                    id=item_id,
                    vector=self._embed_text(self._searchable_text(item)),
                    payload={
                        "source_id": item_id,
                        "dataset_hash": dataset_hash,
                        "source_payload": item,
                    },
                )
            )
        return points

    def _build_dataset_filter(self, dataset_hash: str):
        models = self._models()
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="dataset_hash",
                    match=models.MatchValue(value=dataset_hash),
                )
            ]
        )

    def _models(self):
        from qdrant_client import models

        return models

    def _collection_name(self, project_id: str, item_type: str) -> str:
        return f"{self.collection_prefix}_{project_id.replace('-', '_')}_{item_type}"

    def _dataset_hash(self, items: list[dict[str, Any]]) -> str:
        serialized = json.dumps(items, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()

    def _source_item_id(self, item: dict[str, Any]) -> str:
        source_id = item.get("id")
        if source_id is not None and str(source_id).strip():
            return str(source_id)
        digest = hashlib.sha1(
            json.dumps(item, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return digest

    def _searchable_text(self, item: dict[str, Any]) -> str:
        return " ".join(
            str(value)
            for key, value in item.items()
            if key not in {"id"} and value is not None
        )

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0 for _ in range(self.embedding_dimensions)]
        tokens = tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:2], "big") % self.embedding_dimensions
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            weight = 1.0 + (digest[3] / 255.0)
            vector[bucket] += sign * weight

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def _normalize_qdrant_score(self, score: float) -> float:
        return max(0.0, min(score, 1.0))

    def _merge_results(
        self,
        qdrant_results: list[RetrievedItem],
        lexical_results: list[RetrievedItem],
        limit: int,
    ) -> list[RetrievedItem]:
        merged: dict[str, RetrievedItem] = {}
        for item in qdrant_results + lexical_results:
            key = f"{item.item_type}:{item.item_id}"
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
                continue

            backend = "hybrid" if existing.backend != item.backend else existing.backend
            merged[key] = RetrievedItem(
                item_type=item.item_type,
                item_id=item.item_id,
                score=max(existing.score, item.score),
                payload=item.payload,
                backend=backend,
            )

        ranked = sorted(merged.values(), key=lambda item: item.score, reverse=True)
        return ranked[:limit]


vector_store = HybridVectorStore()
