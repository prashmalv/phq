"""
Qdrant vector store client.
Handles collection creation, upsert, and semantic search.
"""
from typing import Optional
from uuid import uuid4

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from backend.config import settings


class VectorStore:
    def __init__(self):
        self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.collection = settings.QDRANT_COLLECTION
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self._ensure_collection()

    def _ensure_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIM,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection: {self.collection}")

    def embed(self, text: str) -> list[float]:
        return self.model.encode(text).tolist()

    def upsert_event(self, event: dict) -> str:
        """
        Store an enriched event in the vector store.
        event must contain: event_id, content, district, event_type,
                            sentiment, occurred_at, source
        """
        text_to_embed = f"{event.get('event_type', '')} {event['content']}"
        vector = self.embed(text_to_embed)

        point = PointStruct(
            id=str(event.get("event_id", uuid4())),
            vector=vector,
            payload={
                "event_id": str(event.get("event_id")),
                "content": event["content"],
                "source": event.get("source"),
                "event_type": event.get("event_type"),
                "sentiment": event.get("sentiment"),
                "district": event.get("district"),
                "city": event.get("city"),
                "occurred_at": str(event.get("occurred_at")),
                "tags": event.get("tags", []),
                "credibility": event.get("credibility", 0.5),
            },
        )
        self.client.upsert(collection_name=self.collection, points=[point])
        return str(point.id)

    def search(
        self,
        query: str,
        limit: int = 10,
        district: Optional[str] = None,
        event_type: Optional[str] = None,
        min_credibility: float = 0.3,
    ) -> list[dict]:
        """Semantic similarity search with optional filters."""
        vector = self.embed(query)

        must_conditions = []
        if district:
            must_conditions.append(FieldCondition(key="district", match=MatchValue(value=district)))
        if event_type:
            must_conditions.append(FieldCondition(key="event_type", match=MatchValue(value=event_type)))

        query_filter = Filter(must=must_conditions) if must_conditions else None

        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
            score_threshold=0.4,
        )
        return [
            {**r.payload, "score": r.score}
            for r in results
        ]

    def batch_upsert(self, events: list[dict]) -> int:
        points = []
        for event in events:
            text_to_embed = f"{event.get('event_type', '')} {event['content']}"
            vector = self.embed(text_to_embed)
            points.append(
                PointStruct(
                    id=str(event.get("event_id", uuid4())),
                    vector=vector,
                    payload={
                        "event_id": str(event.get("event_id")),
                        "content": event["content"],
                        "source": event.get("source"),
                        "event_type": event.get("event_type"),
                        "district": event.get("district"),
                        "occurred_at": str(event.get("occurred_at")),
                    },
                )
            )
        self.client.upsert(collection_name=self.collection, points=points)
        return len(points)
