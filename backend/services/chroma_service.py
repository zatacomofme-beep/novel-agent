from __future__ import annotations

import asyncio
import hashlib
import math
from dataclasses import dataclass
from typing import Any, Optional

from openai import AsyncOpenAI

from core.config import get_settings

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except ImportError:  # pragma: no cover - 开发机未安装依赖时的兜底
    chromadb = None
    ChromaSettings = None


@dataclass
class ChromaSearchHit:
    entity_type: str
    entity_id: str
    score: float
    content: str
    metadata: dict[str, Any]


class StoryEngineChromaService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: Any | None = None
        self._openai_client: AsyncOpenAI | None = None
        self._memory_index: dict[str, dict[str, dict[str, Any]]] = {}

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
        if chromadb is None:
            collection = self._memory_index.setdefault(project_id, {})
            collection[f"{entity_type}:{entity_id}"] = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "content": content,
                "metadata": metadata or {},
            }
            return
        collection = await self._get_collection(project_id)
        embedding = await self._embed_texts([content])
        payload = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            **(metadata or {}),
        }
        await asyncio.to_thread(
            collection.upsert,
            ids=[f"{entity_type}:{entity_id}"],
            documents=[content],
            metadatas=[payload],
            embeddings=embedding,
        )

    async def delete_document(
        self,
        *,
        project_id: str,
        entity_type: str,
        entity_id: str,
    ) -> None:
        if chromadb is None:
            collection = self._memory_index.setdefault(project_id, {})
            collection.pop(f"{entity_type}:{entity_id}", None)
            return
        collection = await self._get_collection(project_id)
        await asyncio.to_thread(
            collection.delete,
            ids=[f"{entity_type}:{entity_id}"],
        )

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
        if chromadb is None:
            return self._search_memory_index(
                project_id=project_id,
                query=query,
                limit=limit,
                entity_type=entity_type,
            )
        collection = await self._get_collection(project_id)
        embedding = await self._embed_texts([query])
        where = {"entity_type": entity_type} if entity_type else None
        result = await asyncio.to_thread(
            collection.query,
            query_embeddings=embedding,
            n_results=limit,
            where=where,
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: list[ChromaSearchHit] = []
        for index, doc_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) and metadatas[index] else {}
            distance = distances[index] if index < len(distances) else 0.0
            hits.append(
                ChromaSearchHit(
                    entity_type=str(metadata.get("entity_type", "")),
                    entity_id=str(metadata.get("entity_id", doc_id)),
                    score=self._distance_to_score(distance),
                    content=documents[index] if index < len(documents) else "",
                    metadata=metadata,
                )
            )
        return hits

    async def _get_collection(self, project_id: str):
        client = await self._get_client()
        collection_name = f"{self.settings.chroma_collection_prefix}_{project_id.replace('-', '_')}"
        return await asyncio.to_thread(
            client.get_or_create_collection,
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def _get_client(self):
        if self._client is not None:
            return self._client
        if chromadb is None or ChromaSettings is None:
            raise RuntimeError("chromadb package is not installed.")
        try:
            self._client = chromadb.HttpClient(
                host=self.settings.chroma_host,
                port=self.settings.chroma_port,
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=False,
                ),
            )
        except Exception:
            # 在开发环境下，如果 Chroma 容器尚未启动，则自动退回本地内存客户端。
            self._client = chromadb.Client(
                ChromaSettings(
                    anonymized_telemetry=False,
                    is_persistent=False,
                )
            )
        return self._client

    def _search_memory_index(
        self,
        *,
        project_id: str,
        query: str,
        limit: int,
        entity_type: Optional[str],
    ) -> list[ChromaSearchHit]:
        query_tokens = set(query.lower().split())
        collection = self._memory_index.get(project_id, {})
        hits: list[ChromaSearchHit] = []
        for item in collection.values():
            if entity_type and item["entity_type"] != entity_type:
                continue
            content_tokens = set(str(item["content"]).lower().split())
            overlap = len(query_tokens & content_tokens)
            if overlap == 0:
                continue
            hits.append(
                ChromaSearchHit(
                    entity_type=item["entity_type"],
                    entity_id=item["entity_id"],
                    score=round(overlap / max(1, len(query_tokens)), 4),
                    content=item["content"],
                    metadata=item["metadata"],
                )
            )
        return sorted(hits, key=lambda item: item.score, reverse=True)[:limit]

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
        dimensions = self.settings.chroma_embedding_dimensions
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

    def _distance_to_score(self, distance: float | int | None) -> float:
        if distance is None:
            return 0.0
        return round(1.0 / (1.0 + float(distance)), 4)
