"""
Airflow DAG: PHQ Data Ingestion
Runs every 30 minutes — fetches news RSS + Twitter recent search.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "phq-team",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

with DAG(
    dag_id="phq_data_ingestion",
    default_args=default_args,
    description="Ingest news + social media data for PHQ Intelligence Bot",
    schedule_interval="*/30 * * * *",   # every 30 minutes
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["phq", "ingestion"],
) as dag:

    def ingest_news():
        import asyncio
        from aiokafka import AIOKafkaProducer
        from backend.config import settings
        from backend.ingestion.news_ingestor import NewsIngestor

        async def _run():
            producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP)
            await producer.start()
            ingestor = NewsIngestor()
            count = await ingestor.ingest_all(producer)
            await producer.stop()
            await ingestor.close()
            print(f"News ingestion complete: {count} articles")

        asyncio.run(_run())

    def ingest_twitter():
        import asyncio
        from aiokafka import AIOKafkaProducer
        from backend.config import settings
        from backend.ingestion.twitter_ingestor import TwitterIngestor

        if not settings.TWITTER_BEARER_TOKEN:
            print("Twitter API not configured — skipping")
            return

        async def _run():
            producer = AIOKafkaProducer(bootstrap_servers=settings.KAFKA_BOOTSTRAP)
            await producer.start()
            ingestor = TwitterIngestor()
            total = 0
            for query in [
                "Uttar Pradesh violence OR riot OR stampede",
                "उत्तर प्रदेश हिंसा OR दंगा OR भगदड़",
            ]:
                count = await ingestor.search_recent(producer, query, max_results=50)
                total += count
            await producer.stop()
            print(f"Twitter ingestion complete: {total} tweets")

        asyncio.run(_run())

    t1 = PythonOperator(task_id="ingest_news",    python_callable=ingest_news)
    t2 = PythonOperator(task_id="ingest_twitter", python_callable=ingest_twitter)
    t1 >> t2   # run sequentially to stay within rate limits
