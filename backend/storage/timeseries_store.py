"""
TimescaleDB store client.
Handles event persistence and temporal range queries.
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional

import asyncpg
from loguru import logger

from backend.config import settings


class TimeSeriesStore:
    def __init__(self):
        self.dsn = settings.TIMESCALE_DSN
        self._pool: Optional[asyncpg.Pool] = None

    async def init_pool(self):
        self._pool = await asyncpg.create_pool(self.dsn, min_size=2, max_size=10)
        logger.info("TimescaleDB connection pool created")

    async def close(self):
        if self._pool:
            await self._pool.close()

    # ─── Write ───────────────────────────────────────────────────────────────

    async def insert_event(self, event: dict) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO events (
                    event_id, source, source_url, content, content_hi,
                    author_handle, author_verified, language, event_type,
                    sentiment, sentiment_score, credibility,
                    district, tehsil, city, state, lat, lon,
                    tags, entities, raw_data, occurred_at
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,
                    $13,$14,$15,$16,$17,$18,$19,$20,$21,$22
                )
                ON CONFLICT DO NOTHING
                """,
                event.get("event_id"),
                event.get("source"),
                event.get("source_url"),
                event.get("content"),
                event.get("content_hi"),
                event.get("author_handle"),
                event.get("author_verified", False),
                event.get("language"),
                event.get("event_type"),
                event.get("sentiment"),
                event.get("sentiment_score"),
                event.get("credibility", 0.5),
                event.get("district"),
                event.get("tehsil"),
                event.get("city"),
                event.get("state", "Uttar Pradesh"),
                event.get("lat"),
                event.get("lon"),
                event.get("tags", []),
                json.dumps(event.get("entities", {})),
                json.dumps(event.get("raw_data", {})),
                event.get("occurred_at"),
            )

    # ─── Temporal Queries ────────────────────────────────────────────────────

    async def events_in_range(
        self,
        from_date: datetime,
        to_date: datetime,
        district: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        where = "occurred_at BETWEEN $1 AND $2"
        params: list = [from_date, to_date]
        idx = 3

        if district:
            where += f" AND district = ${idx}"
            params.append(district)
            idx += 1
        if event_type:
            where += f" AND event_type = ${idx}"
            params.append(event_type)
            idx += 1

        params.append(limit)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT event_id, source, content, event_type, sentiment,
                       credibility, district, city, occurred_at, tags
                FROM events
                WHERE {where}
                ORDER BY occurred_at DESC
                LIMIT ${idx}
                """,
                *params,
            )
        return [dict(r) for r in rows]

    async def event_count_by_district(
        self,
        from_date: datetime,
        to_date: datetime,
        event_type: Optional[str] = None,
    ) -> list[dict]:
        where = "occurred_at BETWEEN $1 AND $2"
        params: list = [from_date, to_date]
        if event_type:
            where += " AND event_type = $3"
            params.append(event_type)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT district, COUNT(*) AS count,
                       AVG(sentiment_score) AS avg_sentiment
                FROM events
                WHERE {where}
                GROUP BY district
                ORDER BY count DESC
                """,
                *params,
            )
        return [dict(r) for r in rows]

    async def daily_trend(
        self,
        district: str,
        days: int = 30,
        event_type: Optional[str] = None,
    ) -> list[dict]:
        from_date = datetime.utcnow() - timedelta(days=days)
        where = "district = $1 AND occurred_at >= $2"
        params: list = [district, from_date]
        if event_type:
            where += " AND event_type = $3"
            params.append(event_type)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT time_bucket('1 day', occurred_at) AS day,
                       COUNT(*) AS count,
                       AVG(sentiment_score) AS avg_sentiment
                FROM events
                WHERE {where}
                GROUP BY day
                ORDER BY day
                """,
                *params,
            )
        return [dict(r) for r in rows]

    # ─── CAG Cache ───────────────────────────────────────────────────────────

    async def get_cached_answer(self, query_text: str) -> Optional[dict]:
        query_hash = hashlib.sha256(query_text.lower().strip().encode()).hexdigest()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT answer_json FROM cached_answers
                WHERE query_hash = $1 AND expires_at > NOW()
                """,
                query_hash,
            )
            if row:
                await conn.execute(
                    "UPDATE cached_answers SET hit_count = hit_count + 1 WHERE query_hash = $1",
                    query_hash,
                )
                return json.loads(row["answer_json"])
        return None

    async def set_cached_answer(self, query_text: str, answer: dict) -> None:
        query_hash = hashlib.sha256(query_text.lower().strip().encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(seconds=settings.CAG_TTL_SECONDS)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cached_answers (query_hash, query_text, answer_json, expires_at)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (query_hash) DO UPDATE
                SET answer_json = $3, expires_at = $4, hit_count = cached_answers.hit_count + 1
                """,
                query_hash,
                query_text,
                json.dumps(answer),
                expires_at,
            )

    async def log_query(self, audit: dict) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO query_audit
                (officer_id, query_text, query_lang, answer_text, db_sources, latency_ms)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                audit.get("officer_id", "anonymous"),
                audit.get("query_text"),
                audit.get("query_lang"),
                audit.get("answer_text"),
                audit.get("db_sources", []),
                audit.get("latency_ms"),
            )
