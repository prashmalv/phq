"""
News RSS feed ingestion.
Fetches from national + UP regional portals and publishes to Kafka.
"""
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from uuid import uuid4

import feedparser
import httpx
from aiokafka import AIOKafkaProducer
from loguru import logger

from backend.config import settings

# ─── News portal RSS feeds — add/replace as client provides ──────────────────
# These are publicly available feeds. Client should supply internal/restricted feeds.
NEWS_FEEDS = {
    # National Hindi
    "amar_ujala":       "https://www.amarujala.com/rss/uttar-pradesh.xml",
    "dainik_jagran":    "https://www.jagran.com/rss/uttar-pradesh.xml",
    "navbharat_times":  "https://navbharattimes.indiatimes.com/rssfeedsdefault.cms",
    "hindustan":        "https://www.livehindustan.com/rss/uttar-pradesh.xml",
    # National English
    "times_of_india":   "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms",
    "hindustan_times":  "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
    "ndtv":             "https://feeds.feedburner.com/ndtvnews-latest",
    # Regional UP (add more as provided by client)
    "up_tak":           "https://www.uptak.in/rss-feed",
}


class NewsIngestor:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30, follow_redirects=True)

    async def close(self):
        await self.client.aclose()

    async def ingest_all(self, producer: AIOKafkaProducer) -> int:
        total = 0
        for source_name, feed_url in NEWS_FEEDS.items():
            count = await self.ingest_feed(producer, source_name, feed_url)
            logger.info(f"[news] {source_name}: {count} articles")
            total += count
        return total

    async def ingest_feed(
        self, producer: AIOKafkaProducer, source_name: str, feed_url: str
    ) -> int:
        count = 0
        try:
            response = await self.client.get(feed_url)
            response.raise_for_status()
            feed = feedparser.parse(response.text)

            for entry in feed.entries:
                content = f"{entry.get('title', '')} {entry.get('summary', '')}"
                content = content.strip()
                if not content:
                    continue

                # Parse published date
                published_str = entry.get("published") or entry.get("updated")
                try:
                    occurred_at = parsedate_to_datetime(published_str).isoformat()
                except Exception:
                    occurred_at = datetime.now(timezone.utc).isoformat()

                raw = {
                    "event_id": str(uuid4()),
                    "source": "news",
                    "source_url": entry.get("link"),
                    "content": content,
                    "author_handle": source_name,
                    "author_verified": True,   # news portals are considered verified
                    "language": "hi" if self._is_hindi_source(source_name) else "en",
                    "occurred_at": occurred_at,
                    "raw_data": {
                        "feed_source": source_name,
                        "title": entry.get("title"),
                        "tags": [t.get("term", "") for t in entry.get("tags", [])],
                    },
                }
                await producer.send_and_wait(
                    settings.KAFKA_TOPIC_RAW,
                    json.dumps(raw, default=str).encode("utf-8"),
                )
                count += 1
        except Exception as e:
            logger.error(f"Failed to ingest feed {source_name} ({feed_url}): {e}")
        return count

    def _is_hindi_source(self, source_name: str) -> bool:
        hindi_sources = {"amar_ujala", "dainik_jagran", "navbharat_times", "hindustan", "up_tak"}
        return source_name in hindi_sources
