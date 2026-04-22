"""
Kafka enrichment consumer.
Reads raw events from phq.raw.events, enriches them, then writes
to phq.enriched.events and to all three storage backends.
"""
import asyncio
import json
from datetime import datetime

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from loguru import logger

from backend.config import settings
from backend.enrichment.nlp_pipeline import NLPPipeline
from backend.storage.graph_store import GraphStore
from backend.storage.search_store import SearchStore
from backend.storage.timeseries_store import TimeSeriesStore
from backend.storage.vector_store import VectorStore


class EnrichmentWorker:
    def __init__(self):
        self.nlp = NLPPipeline()
        self.vector = VectorStore()
        self.graph = GraphStore()
        self.ts: TimeSeriesStore = None   # async init required
        self.search: SearchStore = None   # async init required

    async def start(self):
        self.ts = TimeSeriesStore()
        await self.ts.init_pool()

        self.search = SearchStore()
        await self.search.init_index()

        consumer = AIOKafkaConsumer(
            settings.KAFKA_TOPIC_RAW,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
        )
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        )

        await consumer.start()
        await producer.start()
        logger.info("Enrichment worker started")

        try:
            async for msg in consumer:
                raw = msg.value
                try:
                    enriched = self.nlp.enrich(raw)
                    await self._persist(enriched)
                    await producer.send_and_wait(settings.KAFKA_TOPIC_ENRICHED, enriched)
                    logger.debug(f"Enriched event {enriched.get('event_id')} → {enriched.get('event_type')}")
                except Exception as e:
                    logger.error(f"Enrichment failed for event: {e}")
        finally:
            await consumer.stop()
            await producer.stop()
            await self.ts.close()
            await self.search.close()
            self.graph.close()

    async def _persist(self, enriched: dict):
        await asyncio.gather(
            self.ts.insert_event(enriched),
            self.search.index_event(enriched),
        )
        self.vector.upsert_event(enriched)
        self.graph.ingest_event(enriched)


if __name__ == "__main__":
    worker = EnrichmentWorker()
    asyncio.run(worker.start())
