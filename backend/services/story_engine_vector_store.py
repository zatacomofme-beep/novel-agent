from __future__ import annotations

import asyncio
import hashlib
import math
from dataclasses import dataclass
from typing import Any, Optional

from openai import AsyncOpenAI

from core.config import get_settings


@dataclass
class ChromaSearchHit:
    entity_type: str
    entity_id: str
    score: float
    content: str
    metadata: dict[str, Any]


class StoryEngineVectorStore:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any | None = None
        self._openai_client: AsyncOpenAI | None = None
        self._qdrant_import_error = False

    async def upsert_document(
        self,
        *,
        project_id: str,
        entity_type: str,
        entity_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not content.strip():
            return
        collection = await self._get_collection(project_id)
        embedding = await self._embed_texts([content])
        point_id = f"{entity_type}:{entity_id}"
        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "content": content,
            **(metadata or {}),
        }
        await asyncio.to_thread(
            collection.upsert,
            points=[
                {
                    "id": point_id,
                    "vector": embedding[0],
                    "payload": payload,
                }
            ],
        )

    async def delete_document(
        self,
        *,
        project_id: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        collection = await self._get_collection(project_id)
        point_id = f"{entity_type}:{entity_id}"
        try:
            await asyncio.to_thread(collection.delete, points_selector=[point_id])
        except Exception:
            pass

    async def search(
        self,
        *,
        project_id: str,
        query: str,
        limit: int = 8,
        entity_type: Optional[str] = None,
    ) -> list[ChromaSearchHit]:
        if not query.strip():
            return []
        collection = await self._get_collection(project_id)
        embedding = await self._embed_texts([query])
        search_params: dict[str, Any] = {"limit": limit}
        if entity_type:
            filter_cond = {"key": "entity_type", "match": {"value": entity_type}}
            search_params["query_filter"] = filter_cond
        result = await asyncio.to_thread(
            collection.search,
            query_vector=embedding[0],
            **search_params,
        )
        hits: list[ChromaSearchHit] = []
        for point in result:
            payload = point.get("payload", {})
            hits.append(
                ChromaSearchHit(
                    entity_type=str(payload.get("entity_type", "")),
                    entity_id=str(payload.get("entity_id", "")),
                    score=float(point.get("score", 0.0)),
                    content=str(payload.get("content", "")),
                    metadata=payload,
                )
            )
        return hits

    async def _get_collection(self, project_id: str):
        client = await self._get_client()
        collection_name = f"{self.settings.qdrant_collection_prefix}_{project_id.replace('-', '_')}"
        await self._ensure_collection(client, collection_name)
        return QdrantCollectionWrapper(client, collection_name)

    async def _ensure_collection(self, client, collection_name: str) -> None:
        try:
            exists = await asyncio.to_thread(client.collection_exists, collection_name)
            if not exists:
                from qdrant_client import models
                await asyncio.to_thread(
                    client.create_collection,
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=self.settings.vector_embedding_dimensions,
                        distance=models.Distance.COSINE,
                    ),
                )
        except Exception:
            pass

    async def _get_client(self):
        if self._qdrant_import_error:
            return None
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import AsyncQdrantClient
        except ImportError:
            self._qdrant_import_error = True
            raise RuntimeError("qdrant-client package is not installed.")
        self._client = AsyncQdrantClient(
            url=self.settings.qdrant_url,
            timeout=self.settings.qdrant_request_timeout_seconds,
        )
        return self._client

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        if self.settings.openai_api_key or self.settings.model_gateway_api_key:
            return await self._embed_texts_with_openai(texts)
        return [self._hash_embed(text) for text in texts]

    async def _embed_texts_with_openai(self, texts: list[str]) -> list[list[float]]:
        if self._openai_client is None:
            client_kwargs: dict[str, Any] = {
                "api_key": self.settings.openai_api_key or self.settings.model_gateway_api_key,
            }
            if self.settings.model_gateway_base_url:
                client_kwargs["base_url"] = self.settings.model_gateway_base_url
            self._openai_client = AsyncOpenAI(**client_kwargs)
        response = await self._openai_client.embeddings.create(
            model=self.settings.story_engine_default_embedding_model,
            input=texts,
        )
        return [list(item.embedding) for item in response.data]

    def _hash_embed(self, text: str) -> list[float]:
        dimensions = self.settings.vector_embedding_dimensions
        vector = [0.0 for _ in range(dimensions)]
        tokens = [token for token in text.lower().split() if token]
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:2], "big") % dimensions
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class QdrantCollectionWrapper:
    def __init__(self, client, collection_name: str):
        self._client = client
        self._collection_name = collection_name

    def upsert(self, points: list[dict[str, Any]]) -> None:
        self._client.upsert(collection_name=self._collection_name, points=points)

    def delete(self, points_selector: list[str]) -> None:
        from qdrant_client.models import PointIdsList
        self._client.delete(
            collection_name=self._collection_name,
            points_selector=PointIdsList(points=points_selector),
        )

    def search(self, query_vector: list[float], **kwargs) -> list[dict[str, Any]]:
        from qdrant_client.models import SearchParams
        results = self._client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            **kwargs,
        )
        return [
            {
                "id": str(hit.id),
                "score": hit.score,
                "payload": hit.payload or {},
            }
            for hit in results
        ]


vector_store = StoryEngineVectorStore()