"""
Central configuration — loaded from environment variables or .env file.
All secrets come from env; defaults are safe for local development only.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ─── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "PHQ Government Intelligence Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ─── MySQL (Matrix Database) ──────────────────────────────────────────────
    MYSQL_HOST: str = "10.242.71.180"
    MYSQL_USER: str = "readUser"
    MYSQL_PASSWORD: str = "readUser@123"
    MYSQL_DATABASE: str = "up_police_matrix"

    # ─── Matrix JWT ───────────────────────────────────────────────────────────
    MATRIX_JWT_SECRET: str = "UPPOLICESOCIALMEDIAjfndfjkjfnkjnfkfjkdfjdfkjdskfjlskfjsldkfjslkdfjslkdsklfjdUPPOLICE"
    MATRIX_JWT_ISSUER: str = "socialMedia"
    MATRIX_JWT_AUDIENCE: str = "socialMediaUsers"

    # ─── Qdrant (Vector DB) ───────────────────────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "phq_events"          # analyzed_data posts
    QDRANT_TOPICS_COLLECTION: str = "phq_topics"   # topic + district_internal_report
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIM: int = 384

    # ─── Neo4j (Graph DB) ─────────────────────────────────────────────────────
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "phq_secure_password"

    # ─── TimescaleDB ──────────────────────────────────────────────────────────
    TIMESCALE_DSN: str = "postgresql://phq_user:phq_secure_password@localhost:5432/phq_events"

    # ─── Elasticsearch ────────────────────────────────────────────────────────
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    ES_INDEX: str = "phq_events"

    # ─── Kafka ────────────────────────────────────────────────────────────────
    KAFKA_BOOTSTRAP: str = "localhost:9092"
    KAFKA_TOPIC_RAW: str = "phq.raw.events"
    KAFKA_TOPIC_ENRICHED: str = "phq.enriched.events"
    KAFKA_CONSUMER_GROUP: str = "phq-enrichment"

    # ─── Redis (CAG cache) ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    CAG_TTL_SECONDS: int = 21600  # 6 hours

    # ─── LLM (Llama 3, local) ─────────────────────────────────────────────────
    LLM_MODEL_PATH: str = "/models/llama3/Meta-Llama-3-8B-Instruct.Q4_K_M.gguf"
    LLM_N_CTX: int = 4096
    LLM_N_GPU_LAYERS: int = 0  # set >0 if GPU available

    # ─── Social Media API Keys ────────────────────────────────────────────────
    TWITTER_BEARER_TOKEN: Optional[str] = None
    TWITTER_API_KEY: Optional[str] = None
    TWITTER_API_SECRET: Optional[str] = None
    TWITTER_ACCESS_TOKEN: Optional[str] = None
    TWITTER_ACCESS_SECRET: Optional[str] = None

    FACEBOOK_ACCESS_TOKEN: Optional[str] = None

    # ─── Keycloak ─────────────────────────────────────────────────────────────
    KEYCLOAK_URL: str = "http://localhost:8180"
    KEYCLOAK_REALM: str = "phq"
    KEYCLOAK_CLIENT_ID: str = "phq-api"
    KEYCLOAK_CLIENT_SECRET: Optional[str] = None

    # ─── Report Generation ────────────────────────────────────────────────────
    SPIKE_THRESHOLD: int = 50         # posts in 6h that trigger an alert report
    REPORT_EMAIL_RECIPIENTS: list[str] = []  # e.g. ["dgp@uppolice.gov.in"]
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None   # sender Gmail address
    SMTP_PASSWORD: Optional[str] = None

    # ─── Geo ──────────────────────────────────────────────────────────────────
    DEFAULT_STATE: str = "Uttar Pradesh"
    UP_DISTRICTS: list[str] = [
        "Agra", "Aligarh", "Ambedkar Nagar", "Amethi", "Amroha",
        "Auraiya", "Azamgarh", "Baghpat", "Bahraich", "Ballia",
        "Balrampur", "Banda", "Barabanki", "Bareilly", "Basti",
        "Bhadohi", "Bijnor", "Budaun", "Bulandshahr", "Chandauli",
        "Chitrakoot", "Deoria", "Etah", "Etawah", "Faizabad",
        "Farrukhabad", "Fatehpur", "Firozabad", "Gautam Buddha Nagar",
        "Ghaziabad", "Ghazipur", "Gonda", "Gorakhpur", "Hamirpur",
        "Hapur", "Hardoi", "Hathras", "Jalaun", "Jaunpur",
        "Jhansi", "Kannauj", "Kanpur Dehat", "Kanpur Nagar",
        "Kasganj", "Kaushambi", "Kheri", "Kushinagar", "Lalitpur",
        "Lucknow", "Maharajganj", "Mahoba", "Mainpuri", "Mathura",
        "Mau", "Meerut", "Mirzapur", "Moradabad", "Muzaffarnagar",
        "Pilibhit", "Pratapgarh", "Prayagraj", "Raebareli", "Rampur",
        "Saharanpur", "Sambhal", "Sant Kabir Nagar", "Shahjahanpur",
        "Shamli", "Shravasti", "Siddharthnagar", "Sitapur", "Sonbhadra",
        "Sultanpur", "Unnao", "Varanasi",
    ]


settings = Settings()
