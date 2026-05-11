"""
Incremental Embedding Sync Service.

Flow:
  1. Read last_synced_id from state file
  2. Pull new records from MySQL (since last_synced_id)
  3. Chunk long posts, generate embeddings
  4. Upsert to Qdrant
  5. Save new last_synced_id

Runs as a background loop (every 60 seconds).
30,000 records/day = ~21 records/minute — well within embedding limits.
"""
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid5, NAMESPACE_URL

from loguru import logger
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, FieldCondition, Filter, MatchValue,
    PointStruct, VectorParams,
)

from backend.config import settings
from backend.sync.mysql_connector import MySQLConnector

# State file — persists last synced ID across restarts
STATE_FILE = Path("sync_state.json")
COLLECTION = settings.QDRANT_COLLECTION
EMBED_DIM = settings.EMBEDDING_DIM
BATCH_SIZE = 200          # records per MySQL fetch
MAX_CHUNK_CHARS = 800     # split posts longer than this


class EmbeddingSync:
    def __init__(self):
        self.mysql = MySQLConnector()
        self.qdrant = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self._ensure_collection()

    # ─── Qdrant setup ────────────────────────────────────────────────────────

    def _ensure_collection(self):
        existing = [c.name for c in self.qdrant.get_collections().collections]
        if COLLECTION not in existing:
            self.qdrant.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
            )
            logger.info(f"Created Qdrant collection: {COLLECTION}")

    # ─── State persistence ───────────────────────────────────────────────────

    def _load_state(self) -> int:
        """Returns last successfully synced post_id (0 if first run)."""
        if STATE_FILE.exists():
            state = json.loads(STATE_FILE.read_text())
            return state.get("last_synced_id", 0)
        return 0

    def _save_state(self, last_id: int):
        STATE_FILE.write_text(json.dumps({
            "last_synced_id": last_id,
            "last_synced_at": datetime.utcnow().isoformat(),
        }))

    # ─── Core sync ───────────────────────────────────────────────────────────

    def sync_once(self) -> int:
        """
        Single sync cycle. Returns count of records embedded.
        """
        since_id = self._load_state()
        total_embedded = 0

        while True:
            records = self.mysql.get_new_records(since_id, batch_size=BATCH_SIZE)
            if not records:
                break

            points = []
            for record in records:
                chunks = self._chunk_record(record)
                for chunk_text, chunk_idx in chunks:
                    vec = self.model.encode(chunk_text).tolist()
                    # Deterministic ID: same post+chunk always gets same vector ID
                    point_id = str(uuid5(NAMESPACE_URL, f"{record['post_id']}_{chunk_idx}"))
                    points.append(PointStruct(
                        id=point_id,
                        vector=vec,
                        payload=self._make_payload(record, chunk_text, chunk_idx),
                    ))

            if points:
                self.qdrant.upsert(collection_name=COLLECTION, points=points)
                total_embedded += len(points)

            max_id = max(r["post_id"] for r in records)
            since_id = max_id
            self._save_state(max_id)
            logger.info(f"Synced batch: {len(records)} records → {len(points)} vectors. last_id={max_id}")

            if len(records) < BATCH_SIZE:
                break  # caught up to latest

        return total_embedded

    # ─── Chunking ────────────────────────────────────────────────────────────

    def _chunk_record(self, record: dict) -> list[tuple[str, int]]:
        """
        Returns list of (chunk_text, chunk_index) tuples.
        Short posts → single chunk with metadata prefix.
        Long posts → split into overlapping windows.
        """
        content = (record.get("content") or "").strip()
        if not content:
            return []

        # Metadata prefix for every chunk — helps retrieval context
        meta = self._build_meta_prefix(record)
        full_text = f"{meta}{content}"

        if len(full_text) <= MAX_CHUNK_CHARS:
            return [(full_text, 0)]

        # Sliding window chunking with 100-char overlap
        chunks = []
        step = MAX_CHUNK_CHARS - 100
        for i, start in enumerate(range(0, len(content), step)):
            chunk_content = content[start:start + MAX_CHUNK_CHARS]
            chunks.append((f"{meta}{chunk_content}", i))
            if start + MAX_CHUNK_CHARS >= len(content):
                break
        return chunks

    def _build_meta_prefix(self, record: dict) -> str:
        parts = []
        if record.get("platform"):
            parts.append(record["platform"])
        if record.get("district"):
            parts.append(record["district"])
        if record.get("language"):
            parts.append(f"lang:{record['language']}")
        if record.get("created_at"):
            parts.append(str(record["created_at"])[:10])
        return f"[{' | '.join(parts)}] " if parts else ""

    def _make_payload(self, record: dict, chunk_text: str, chunk_idx: int) -> dict:
        return {
            "post_id":    record["post_id"],
            "chunk_idx":  chunk_idx,
            "content":    chunk_text[:500],      # store trimmed for payload
            "platform":   record.get("platform"),
            "author":     record.get("author"),
            "language":   record.get("language"),
            "district":   record.get("district"),
            "source_url": record.get("source_url"),
            "created_at": str(record.get("created_at", "")),
        }

    # ─── Continuous loop ─────────────────────────────────────────────────────

    async def run_forever(self, interval_seconds: int = 60):
        """
        Runs sync every `interval_seconds`.
        100 posts/min → check every 60s is sufficient.
        """
        logger.info(f"Embedding sync started (interval={interval_seconds}s)")
        while True:
            try:
                t0 = time.monotonic()
                count = self.sync_once()
                elapsed = time.monotonic() - t0
                if count:
                    logger.info(f"Sync complete: {count} vectors in {elapsed:.1f}s")
            except Exception as e:
                logger.error(f"Sync cycle failed: {e}")
            await asyncio.sleep(interval_seconds)

    # ─── Initial historical backfill ─────────────────────────────────────────

    def backfill(self, from_id: int = 0):
        """
        One-time backfill of all historical data (6 months).
        Run manually once on first deploy.
        """
        logger.info(f"Starting historical backfill from post_id={from_id}")
        total = 0
        since_id = from_id
        while True:
            records = self.mysql.get_new_records(since_id, batch_size=500)
            if not records:
                break
            points = []
            for record in records:
                for chunk_text, chunk_idx in self._chunk_record(record):
                    vec = self.model.encode(chunk_text).tolist()
                    point_id = str(uuid5(NAMESPACE_URL, f"{record['post_id']}_{chunk_idx}"))
                    points.append(PointStruct(
                        id=point_id,
                        vector=vec,
                        payload=self._make_payload(record, chunk_text, chunk_idx),
                    ))
            if points:
                self.qdrant.upsert(collection_name=COLLECTION, points=points)
            since_id = max(r["post_id"] for r in records)
            total += len(records)
            self._save_state(since_id)
            logger.info(f"Backfilled {total} records... last_id={since_id}")
        logger.info(f"Backfill complete. Total: {total} records.")


if __name__ == "__main__":
    import sys
    syncer = EmbeddingSync()
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        syncer.backfill()
    else:
        asyncio.run(syncer.run_forever())
