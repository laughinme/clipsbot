from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse

from core.config import Settings, get_settings


class QdrantService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._collection_ready = False
        self._ensure_lock = asyncio.Lock()
        if settings.QDRANT_LOCAL_PATH:
            if settings.QDRANT_LOCAL_PATH == ":memory:":
                self._client = QdrantClient(":memory:")
            else:
                self._client = QdrantClient(path=settings.QDRANT_LOCAL_PATH)
        else:
            self._client = QdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
                check_compatibility=False,
            )

    async def ensure_collection(self) -> None:
        if self._collection_ready:
            return
        async with self._ensure_lock:
            if self._collection_ready:
                return
            exists = await asyncio.to_thread(self._client.collection_exists, self.settings.QDRANT_COLLECTION)
            if not exists:
                await asyncio.to_thread(
                    self._client.create_collection,
                    collection_name=self.settings.QDRANT_COLLECTION,
                    vectors_config=models.VectorParams(
                        size=self.settings.EMBEDDING_VECTOR_SIZE,
                        distance=models.Distance.COSINE,
                    ),
                )
            self._collection_ready = True

    async def check_health(self) -> None:
        await asyncio.to_thread(self._client.get_collections)
        await self.ensure_collection()

    async def reset_collection(self) -> None:
        exists = await asyncio.to_thread(self._client.collection_exists, self.settings.QDRANT_COLLECTION)
        if exists:
            await asyncio.to_thread(self._client.delete_collection, self.settings.QDRANT_COLLECTION)
        self._collection_ready = False
        await self.ensure_collection()

    async def _run_with_collection_recovery(self, operation):
        try:
            return await operation()
        except UnexpectedResponse as exc:
            if exc.status_code != 404:
                raise
            self._collection_ready = False
            await self.ensure_collection()
            return await operation()

    async def upsert_point(
        self,
        *,
        point_id: str,
        vector: list[float],
        payload: dict[str, Any],
    ) -> None:
        await self.ensure_collection()
        await self._run_with_collection_recovery(
            lambda: asyncio.to_thread(
                self._client.upsert,
                collection_name=self.settings.QDRANT_COLLECTION,
                wait=True,
                points=[
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=payload,
                    )
                ],
            )
        )

    async def upsert_points(self, points: list[models.PointStruct]) -> None:
        if not points:
            return
        await self.ensure_collection()
        await self._run_with_collection_recovery(
            lambda: asyncio.to_thread(
                self._client.upsert,
                collection_name=self.settings.QDRANT_COLLECTION,
                wait=True,
                points=points,
            )
        )

    async def query(
        self,
        *,
        vector: list[float],
        limit: int,
        query_filter: models.Filter | None = None,
    ) -> list[models.ScoredPoint]:
        await self.ensure_collection()
        result = await self._run_with_collection_recovery(
            lambda: asyncio.to_thread(
                self._client.query_points,
                collection_name=self.settings.QDRANT_COLLECTION,
                query=vector,
                query_filter=query_filter,
                limit=limit,
            )
        )
        return list(result.points)

    async def get_point_vector(self, point_id: str) -> list[float]:
        await self.ensure_collection()
        points = await self._run_with_collection_recovery(
            lambda: asyncio.to_thread(
                self._client.retrieve,
                collection_name=self.settings.QDRANT_COLLECTION,
                ids=[point_id],
                with_vectors=True,
                with_payload=False,
            )
        )
        if not points:
            raise RuntimeError(f"Qdrant point {point_id} not found")
        raw_vector = points[0].vector
        if isinstance(raw_vector, dict):
            raw_vector = next(iter(raw_vector.values()))
        if not isinstance(raw_vector, list):
            raise RuntimeError(f"Unexpected Qdrant vector payload for point {point_id}")
        return [float(value) for value in raw_vector]


@lru_cache
def get_qdrant_service() -> QdrantService:
    return QdrantService(get_settings())


def clear_qdrant_service_cache() -> None:
    get_qdrant_service.cache_clear()
