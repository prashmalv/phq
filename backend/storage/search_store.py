"""
Elasticsearch full-text search client.
Handles index creation and keyword/phrase queries.
"""
from datetime import datetime
from typing import Optional

from elasticsearch import AsyncElasticsearch
from loguru import logger

from backend.config import settings

INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "hindi_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "stop"],
                },
            }
        },
    },
    "mappings": {
        "properties": {
            "event_id":     {"type": "keyword"},
            "content":      {"type": "text", "analyzer": "standard"},
            "content_hi":   {"type": "text", "analyzer": "hindi_analyzer"},
            "source":       {"type": "keyword"},
            "event_type":   {"type": "keyword"},
            "sentiment":    {"type": "integer"},
            "district":     {"type": "keyword"},
            "city":         {"type": "keyword"},
            "author_handle":{"type": "keyword"},
            "tags":         {"type": "keyword"},
            "occurred_at":  {"type": "date"},
        }
    },
}


class SearchStore:
    def __init__(self):
        self.es = AsyncElasticsearch(settings.ELASTICSEARCH_URL)
        self.index = settings.ES_INDEX

    async def init_index(self):
        exists = await self.es.indices.exists(index=self.index)
        if not exists:
            await self.es.indices.create(index=self.index, body=INDEX_MAPPING)
            logger.info(f"Created Elasticsearch index: {self.index}")

    async def close(self):
        await self.es.close()

    async def index_event(self, event: dict) -> None:
        doc = {
            "event_id":      str(event.get("event_id")),
            "content":       event.get("content"),
            "content_hi":    event.get("content_hi"),
            "source":        event.get("source"),
            "event_type":    event.get("event_type"),
            "sentiment":     event.get("sentiment", 0),
            "district":      event.get("district"),
            "city":          event.get("city"),
            "author_handle": event.get("author_handle"),
            "tags":          event.get("tags", []),
            "occurred_at":   event.get("occurred_at"),
        }
        await self.es.index(
            index=self.index,
            id=str(event.get("event_id")),
            document=doc,
        )

    async def keyword_search(
        self,
        query: str,
        district: Optional[str] = None,
        event_type: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 20,
    ) -> list[dict]:
        must: list = [
            {
                "multi_match": {
                    "query": query,
                    "fields": ["content^2", "content_hi^2", "tags", "author_handle"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                }
            }
        ]
        filters: list = []

        if district:
            filters.append({"term": {"district": district}})
        if event_type:
            filters.append({"term": {"event_type": event_type}})
        if from_date or to_date:
            date_range: dict = {}
            if from_date:
                date_range["gte"] = from_date.isoformat()
            if to_date:
                date_range["lte"] = to_date.isoformat()
            filters.append({"range": {"occurred_at": date_range}})

        body = {
            "query": {"bool": {"must": must, "filter": filters}},
            "sort": [{"occurred_at": "desc"}],
            "size": limit,
        }
        response = await self.es.search(index=self.index, body=body)
        return [
            {**hit["_source"], "score": hit["_score"]}
            for hit in response["hits"]["hits"]
        ]

    async def hashtag_search(self, hashtag: str, limit: int = 20) -> list[dict]:
        body = {
            "query": {
                "bool": {
                    "should": [
                        {"term": {"tags": hashtag}},
                        {"match_phrase": {"content": hashtag}},
                    ]
                }
            },
            "size": limit,
            "sort": [{"occurred_at": "desc"}],
        }
        response = await self.es.search(index=self.index, body=body)
        return [hit["_source"] for hit in response["hits"]["hits"]]
