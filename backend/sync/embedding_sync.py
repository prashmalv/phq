"""
Incremental Embedding Sync Service.

Three source tables, two Qdrant collections:
  phq_events  ← analyzed_data  (1.4M rows, ~30k/day)
  phq_topics  ← topic          (301k rows, re-embedded on update)
               + district_internal_report  (1k rows, official reports)

State file tracks a separate watermark per table so each can catch up
independently.  Topics also have an updated_at watermark for re-syncing
records that get enriched after initial insert.

Flow per cycle:
  1. Pull new analyzed_data rows (since last analyzed_data id)
  2. Pull new topic rows        (since last topic id)
  3. Pull updated topic rows    (since last topic updated_at seen)
  4. Pull new internal reports  (since last report id)
  5. Upsert all batches to Qdrant, persist state
"""
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

from backend.config import settings
from backend.sync.mysql_connector import MySQLConnector

STATE_FILE = Path("sync_state.json")

COLLECTION_EVENTS = settings.QDRANT_COLLECTION         # phq_events
COLLECTION_TOPICS = settings.QDRANT_TOPICS_COLLECTION  # phq_topics
EMBED_DIM = settings.EMBEDDING_DIM

BATCH_EVENTS  = 300
BATCH_TOPICS  = 200
BATCH_REPORTS = 50
MAX_CHUNK_CHARS = 800
CHUNK_OVERLAP   = 100


class EmbeddingSync:
    def __init__(self):
        self.mysql = MySQLConnector()
        self.qdrant = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        self._ensure_collections()

    # ─── Qdrant setup ────────────────────────────────────────────────────────

    def _ensure_collections(self):
        existing = {c.name for c in self.qdrant.get_collections().collections}
        for name in (COLLECTION_EVENTS, COLLECTION_TOPICS):
            if name not in existing:
                self.qdrant.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {name}")

    # ─── State persistence ───────────────────────────────────────────────────

    def _load_state(self) -> dict:
        if STATE_FILE.exists():
            return json.loads(STATE_FILE.read_text())
        return {
            "analyzed_data_last_id": 0,
            "topic_last_id": 0,
            "topic_last_updated_at": "2020-01-01 00:00:00",
            "report_last_id": 0,
            "last_synced_at": None,
        }

    def _save_state(self, state: dict):
        state["last_synced_at"] = datetime.utcnow().isoformat()
        STATE_FILE.write_text(json.dumps(state, default=str))

    # ─── Chunking helpers ─────────────────────────────────────────────────────

    def _chunks(self, text: str, prefix: str) -> list[tuple[str, int]]:
        """Split text with sliding window. Returns (chunk_text, chunk_index) pairs."""
        text = text.strip()
        if not text:
            return []
        full = f"{prefix}{text}"
        if len(full) <= MAX_CHUNK_CHARS:
            return [(full, 0)]
        step = MAX_CHUNK_CHARS - CHUNK_OVERLAP
        result = []
        for i, start in enumerate(range(0, len(text), step)):
            part = text[start : start + MAX_CHUNK_CHARS]
            result.append((f"{prefix}{part}", i))
            if start + MAX_CHUNK_CHARS >= len(text):
                break
        return result

    # ─── analyzed_data embedding ──────────────────────────────────────────────

    def _post_text(self, r: dict) -> str:
        """Build rich embedding text for a single analyzed_data row."""
        parts = []
        # Prefer enhanced_text > content (post_bank_post_snippet)
        body = (r.get("enhanced_text") or r.get("content") or "").strip()
        context = (r.get("contextual_understanding") or "").strip()
        incidents = (r.get("incidents") or "").strip()
        if body:
            parts.append(body)
        if context and context != body:
            parts.append(f"Context: {context}")
        if incidents:
            parts.append(f"Incidents: {incidents}")
        return "\n".join(parts)

    def _post_prefix(self, r: dict) -> str:
        platform = r.get("platform") or ""
        district = r.get("district") or ""
        event_type = r.get("event_type") or ""
        date = str(r.get("occurred_at") or r.get("created_at") or "")[:10]
        tags = " | ".join(filter(None, [platform, district, event_type, date]))
        return f"[{tags}] " if tags else ""

    def _post_payload(self, r: dict, chunk_text: str, chunk_idx: int) -> dict:
        return {
            "source_table":   "analyzed_data",
            "record_id":      r["id"],
            "chunk_idx":      chunk_idx,
            "content":        chunk_text[:500],
            "platform":       r.get("platform"),
            "source_detail":  r.get("source_detail"),
            "author":         r.get("author"),
            "author_name":    r.get("author_name"),
            "language":       r.get("language"),
            "district":       r.get("district"),
            "thana":          r.get("thana"),
            "location":       r.get("location_str"),
            "event_type":     r.get("event_type"),
            "sub_event_type": r.get("sub_event_type"),
            "sentiment":      r.get("sentiment"),
            "sentiment_confidence": r.get("sentiment_confidence"),
            "emotion":        r.get("emotion"),
            "emotion2":       r.get("emotion2"),
            "emotional_intensity": r.get("emotional_intensity"),
            "person_names":   r.get("person_names"),
            "org_names":      r.get("organisation_names"),
            "district_names": r.get("district_names"),
            "hashtags":       r.get("hashtags"),
            "keywords":       r.get("keywords_cloud"),
            "topic_id":       r.get("unique_topic_id"),
            "topic_title":    r.get("topic_title"),
            "source_url":     r.get("source_url"),
            "likes":          r.get("likes"),
            "views":          r.get("views"),
            "retweets":       r.get("retweets"),
            "occurred_at":    str(r.get("occurred_at") or ""),
            "created_at":     str(r.get("created_at") or ""),
        }

    def _sync_analyzed_data(self, state: dict) -> int:
        since_id = state["analyzed_data_last_id"]
        total = 0
        while True:
            rows = self.mysql.get_analyzed_data(since_id, batch_size=BATCH_EVENTS)
            if not rows:
                break
            points = []
            for r in rows:
                text = self._post_text(r)
                prefix = self._post_prefix(r)
                for chunk_text, chunk_idx in self._chunks(text, prefix):
                    vec = self.model.encode(chunk_text).tolist()
                    pid = str(uuid5(NAMESPACE_URL, f"ad_{r['id']}_{chunk_idx}"))
                    points.append(PointStruct(
                        id=pid, vector=vec,
                        payload=self._post_payload(r, chunk_text, chunk_idx),
                    ))
            if points:
                self.qdrant.upsert(collection_name=COLLECTION_EVENTS, points=points)
                total += len(points)
            max_id = max(r["id"] for r in rows)
            since_id = max_id
            state["analyzed_data_last_id"] = max_id
            logger.info(f"[analyzed_data] batch {len(rows)} rows → {len(points)} vectors, last_id={max_id}")
            if len(rows) < BATCH_EVENTS:
                break
        return total

    # ─── topic embedding ──────────────────────────────────────────────────────

    def _topic_text(self, r: dict) -> str:
        parts = []
        title = (r.get("topic_title") or "").strip()
        cmd_desc = (r.get("command_center_description") or "").strip()
        int_desc = (r.get("int_description") or "").strip()
        keywords = (r.get("keywords_cloud") or "").strip()
        if title:
            parts.append(title)
        desc = cmd_desc or int_desc
        if desc:
            parts.append(desc)
        if keywords:
            parts.append(f"Keywords: {keywords}")
        return "\n".join(parts)

    def _topic_prefix(self, r: dict) -> str:
        category = r.get("broad_category") or ""
        districts = r.get("primary_districts") or ""
        tags = " | ".join(filter(None, ["Topic", category, districts]))
        return f"[{tags}] " if tags else "[Topic] "

    def _topic_payload(self, r: dict, chunk_text: str, chunk_idx: int) -> dict:
        return {
            "source_table":   "topic",
            "record_id":      r["id"],
            "unique_topic_id": r.get("unique_topic_id"),
            "chunk_idx":      chunk_idx,
            "content":        chunk_text[:500],
            "topic_title":    r.get("topic_title"),
            "event_type":     r.get("broad_category"),
            "sub_event_type": r.get("sub_category"),
            "district":       r.get("primary_districts"),
            "thana":          r.get("primary_thana"),
            "location":       r.get("primary_location"),
            "hashtags":       r.get("hashtags"),
            "keywords":       r.get("keywords_cloud"),
            "total_posts":    r.get("total_no_of_post"),
            "topic_status":   r.get("topic_status"),
            "created_at":     str(r.get("created_at") or ""),
            "updated_at":     str(r.get("updated_at") or ""),
        }

    def _sync_topics_new(self, state: dict) -> int:
        since_id = state["topic_last_id"]
        total = 0
        while True:
            rows = self.mysql.get_topics(since_id, batch_size=BATCH_TOPICS)
            if not rows:
                break
            points = []
            for r in rows:
                text = self._topic_text(r)
                prefix = self._topic_prefix(r)
                for chunk_text, chunk_idx in self._chunks(text, prefix):
                    vec = self.model.encode(chunk_text).tolist()
                    pid = str(uuid5(NAMESPACE_URL, f"topic_{r['id']}_{chunk_idx}"))
                    points.append(PointStruct(
                        id=pid, vector=vec,
                        payload=self._topic_payload(r, chunk_text, chunk_idx),
                    ))
            if points:
                self.qdrant.upsert(collection_name=COLLECTION_TOPICS, points=points)
                total += len(points)
            max_id = max(r["id"] for r in rows)
            since_id = max_id
            state["topic_last_id"] = max_id
            logger.info(f"[topic new] batch {len(rows)} rows → {len(points)} vectors, last_id={max_id}")
            if len(rows) < BATCH_TOPICS:
                break
        return total

    def _sync_topics_updated(self, state: dict) -> int:
        """Re-embed topics that were updated after last seen updated_at."""
        since_ts = state["topic_last_updated_at"]
        rows = self.mysql.get_updated_topics(since_ts, limit=BATCH_TOPICS)
        if not rows:
            return 0
        points = []
        for r in rows:
            text = self._topic_text(r)
            prefix = self._topic_prefix(r)
            for chunk_text, chunk_idx in self._chunks(text, prefix):
                vec = self.model.encode(chunk_text).tolist()
                # Same deterministic ID → upsert overwrites stale vector
                pid = str(uuid5(NAMESPACE_URL, f"topic_{r['id']}_{chunk_idx}"))
                points.append(PointStruct(
                    id=pid, vector=vec,
                    payload=self._topic_payload(r, chunk_text, chunk_idx),
                ))
        if points:
            self.qdrant.upsert(collection_name=COLLECTION_TOPICS, points=points)
        max_ts = max(str(r["updated_at"]) for r in rows)
        state["topic_last_updated_at"] = max_ts
        logger.info(f"[topic updated] {len(rows)} rows re-embedded, last_updated_at={max_ts}")
        return len(points)

    # ─── district_internal_report embedding ───────────────────────────────────

    def _report_text(self, r: dict) -> str:
        parts = []
        desc = (r.get("incident_description") or "").strip()
        crime = (r.get("crime_type") or "").strip()
        accused = (r.get("accused_names") or "").strip()
        victim = (r.get("victim_name") or "").strip()
        remark = (r.get("final_remark") or r.get("headquater_remark") or "").strip()
        if desc:
            parts.append(desc)
        if crime:
            parts.append(f"Crime: {crime}")
        if accused:
            parts.append(f"Accused: {accused}")
        if victim:
            parts.append(f"Victim: {victim}")
        if remark:
            parts.append(f"Remark: {remark}")
        return "\n".join(parts)

    def _report_prefix(self, r: dict) -> str:
        district = r.get("district") or ""
        thana = r.get("thana") or ""
        date = str(r.get("incident_date_time") or r.get("creation_date") or "")[:10]
        tags = " | ".join(filter(None, ["Official Report", district, thana, date]))
        return f"[{tags}] "

    def _report_payload(self, r: dict, chunk_text: str, chunk_idx: int) -> dict:
        return {
            "source_table":    "district_internal_report",
            "record_id":       r["id"],
            "chunk_idx":       chunk_idx,
            "content":         chunk_text[:500],
            "district":        r.get("district"),
            "thana":           r.get("thana"),
            "event_type":      r.get("crime_type"),
            "person_names":    r.get("accused_names"),
            "victim_name":     r.get("victim_name"),
            "arrest_status":   r.get("arrest_status"),
            "final_remark":    r.get("final_remark"),
            "hq_remark":       r.get("headquater_remark"),
            "dgp_remark":      r.get("dgp_remark"),
            "topic_id":        r.get("unique_topic_id"),
            "occurred_at":     str(r.get("incident_date_time") or ""),
            "created_at":      str(r.get("creation_date") or ""),
            # High-credibility flag so the agent can surface these preferentially
            "is_official_report": True,
        }

    def _sync_reports(self, state: dict) -> int:
        since_id = state["report_last_id"]
        total = 0
        while True:
            rows = self.mysql.get_internal_reports(since_id, batch_size=BATCH_REPORTS)
            if not rows:
                break
            points = []
            for r in rows:
                text = self._report_text(r)
                prefix = self._report_prefix(r)
                for chunk_text, chunk_idx in self._chunks(text, prefix):
                    vec = self.model.encode(chunk_text).tolist()
                    pid = str(uuid5(NAMESPACE_URL, f"rpt_{r['id']}_{chunk_idx}"))
                    points.append(PointStruct(
                        id=pid, vector=vec,
                        payload=self._report_payload(r, chunk_text, chunk_idx),
                    ))
            if points:
                self.qdrant.upsert(collection_name=COLLECTION_TOPICS, points=points)
                total += len(points)
            max_id = max(r["id"] for r in rows)
            since_id = max_id
            state["report_last_id"] = max_id
            logger.info(f"[reports] batch {len(rows)} rows → {len(points)} vectors, last_id={max_id}")
            if len(rows) < BATCH_REPORTS:
                break
        return total

    # ─── Main sync cycle ──────────────────────────────────────────────────────

    def sync_once(self) -> int:
        state = self._load_state()
        total = 0
        total += self._sync_analyzed_data(state)
        total += self._sync_topics_new(state)
        total += self._sync_topics_updated(state)
        total += self._sync_reports(state)
        self._save_state(state)
        return total

    async def run_forever(self, interval_seconds: int = 60):
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

    # ─── One-time historical backfill ─────────────────────────────────────────

    def backfill(self, from_analyzed_id: int = 0):
        """
        Run once on first deploy to backfill all historical data.
        Resets only the analyzed_data watermark so topics/reports still
        use their existing state.
        """
        logger.info(f"Starting backfill from analyzed_data id={from_analyzed_id}")
        state = self._load_state()
        state["analyzed_data_last_id"] = from_analyzed_id
        total = 0
        while True:
            rows = self.mysql.get_analyzed_data(
                state["analyzed_data_last_id"], batch_size=500
            )
            if not rows:
                break
            points = []
            for r in rows:
                text = self._post_text(r)
                prefix = self._post_prefix(r)
                for chunk_text, chunk_idx in self._chunks(text, prefix):
                    vec = self.model.encode(chunk_text).tolist()
                    pid = str(uuid5(NAMESPACE_URL, f"ad_{r['id']}_{chunk_idx}"))
                    points.append(PointStruct(
                        id=pid, vector=vec,
                        payload=self._post_payload(r, chunk_text, chunk_idx),
                    ))
            if points:
                self.qdrant.upsert(collection_name=COLLECTION_EVENTS, points=points)
            state["analyzed_data_last_id"] = max(r["id"] for r in rows)
            total += len(rows)
            self._save_state(state)
            logger.info(f"Backfilled {total} rows... last_id={state['analyzed_data_last_id']}")
        logger.info(f"Backfill complete. Total: {total} rows.")


if __name__ == "__main__":
    import sys
    syncer = EmbeddingSync()
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        syncer.backfill()
    else:
        asyncio.run(syncer.run_forever())
