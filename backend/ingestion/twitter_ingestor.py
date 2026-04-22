"""
Twitter/X ingestion connector.
Uses Twitter API v2 (filtered stream + recent search).
Publishes raw events to Kafka topic: phq.raw.events
"""
import json
from datetime import datetime, timezone
from uuid import uuid4

import tweepy
from aiokafka import AIOKafkaProducer
from loguru import logger

from backend.config import settings


# UP-specific search queries — tailor with client after onboarding
UP_SEARCH_QUERIES = [
    # English
    "Uttar Pradesh violence OR riot OR stampede OR protest OR accident",
    "UP crime OR murder OR riot lang:en",
    # Hindi
    "उत्तर प्रदेश हिंसा OR दंगा OR भगदड़ OR विरोध",
    "यूपी हत्या OR दुर्घटना OR आग",
]

# Geofence for UP (approx bounding box)
UP_GEO = "27.0,80.0,30km"  # centroid near Lucknow — adjust per district need


class TwitterIngestor:
    def __init__(self):
        if not settings.TWITTER_BEARER_TOKEN:
            raise ValueError("TWITTER_BEARER_TOKEN not configured")
        self.client = tweepy.Client(
            bearer_token=settings.TWITTER_BEARER_TOKEN,
            consumer_key=settings.TWITTER_API_KEY,
            consumer_secret=settings.TWITTER_API_SECRET,
            access_token=settings.TWITTER_ACCESS_TOKEN,
            access_token_secret=settings.TWITTER_ACCESS_SECRET,
            wait_on_rate_limit=True,
        )

    async def search_recent(
        self,
        producer: AIOKafkaProducer,
        query: str,
        max_results: int = 100,
    ) -> int:
        """
        Search last 7 days of tweets matching query.
        Returns count of events published to Kafka.
        """
        count = 0
        try:
            paginator = tweepy.Paginator(
                self.client.search_recent_tweets,
                query=f"{query} -is:retweet lang:hi OR lang:en",
                tweet_fields=["created_at", "author_id", "entities", "geo", "lang", "public_metrics"],
                user_fields=["name", "username", "verified"],
                expansions=["author_id", "geo.place_id"],
                max_results=min(max_results, 100),
            ).flatten(limit=max_results)

            for tweet in paginator:
                raw = self._to_raw_event(tweet)
                await producer.send_and_wait(
                    settings.KAFKA_TOPIC_RAW,
                    json.dumps(raw, default=str).encode("utf-8"),
                )
                count += 1
        except Exception as e:
            logger.error(f"Twitter search failed for '{query}': {e}")
        return count

    def _to_raw_event(self, tweet) -> dict:
        return {
            "event_id": str(uuid4()),
            "source": "twitter",
            "source_url": f"https://twitter.com/i/web/status/{tweet.id}",
            "content": tweet.text,
            "author_handle": str(tweet.author_id),
            "author_verified": False,  # v2 API: check User expansion
            "language": tweet.lang,
            "occurred_at": tweet.created_at.isoformat() if tweet.created_at else datetime.now(timezone.utc).isoformat(),
            "raw_data": {
                "tweet_id": str(tweet.id),
                "metrics": tweet.public_metrics,
            },
        }


class TwitterStreamIngestor(tweepy.StreamingClient):
    """
    Real-time filtered stream for UP keywords.
    Requires Twitter API v2 Elevated access.
    """
    def __init__(self, producer: AIOKafkaProducer):
        super().__init__(settings.TWITTER_BEARER_TOKEN, wait_on_rate_limit=True)
        self.producer = producer

    def on_tweet(self, tweet):
        raw = {
            "event_id": str(uuid4()),
            "source": "twitter",
            "source_url": f"https://twitter.com/i/web/status/{tweet.id}",
            "content": tweet.text,
            "language": getattr(tweet, "lang", None),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "raw_data": {"tweet_id": str(tweet.id)},
        }
        import asyncio
        asyncio.create_task(
            self.producer.send_and_wait(
                settings.KAFKA_TOPIC_RAW,
                json.dumps(raw, default=str).encode("utf-8"),
            )
        )

    def on_error(self, status):
        logger.error(f"Twitter stream error: {status}")

    def setup_rules(self):
        """Set UP-specific filter rules on the stream."""
        existing = self.get_rules().data or []
        if existing:
            self.delete_rules([r.id for r in existing])
        for query in UP_SEARCH_QUERIES[:5]:  # max 5 rules on basic tier
            self.add_rules(tweepy.StreamRule(query[:512]))
        logger.info("Twitter stream rules updated")
