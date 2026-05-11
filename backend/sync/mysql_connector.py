"""
MySQL connector for Matrix database (up_police_matrix).
Read-only access via ZeroTier VPN.

IMPORTANT: Column names below are PLACEHOLDERS.
Replace with actual column names after running scripts/extract_schema.py
and sharing the output.
"""
import pymysql
import pymysql.cursors
from contextlib import contextmanager
from loguru import logger
from backend.config import settings


# ─── PLACEHOLDER COLUMN MAPPING ──────────────────────────────────────────────
# Update these after receiving actual schema from client
# Format: our_name → actual_mysql_column_name

COLUMN_MAP = {
    "post_id":        "id",              # UPDATE: primary key column name
    "content":        "content",         # UPDATE: main text column
    "platform":       "platform",        # UPDATE: twitter/facebook/instagram etc
    "author":         "author",          # UPDATE: username/handle
    "author_verified":"is_verified",     # UPDATE: boolean verified column
    "language":       "detected_language", # UPDATE: language column (confirmed exists)
    "district":       "district",        # UPDATE: district column
    "location":       "location",        # UPDATE: city/location column
    "created_at":     "created_at",      # UPDATE: timestamp column
    "source_url":     "url",             # UPDATE: original post URL
    "image_url":      "image_url",       # UPDATE: image link if any
    "video_url":      "video_url",       # UPDATE: video link if any
    "likes":          "likes_count",     # UPDATE: engagement metric
    "shares":         "shares_count",    # UPDATE: shares/retweets
    "comments":       "comments_count",  # UPDATE: comments count
    "category":       "category",        # UPDATE: event category if exists, else None
    "sentiment":      "sentiment",       # UPDATE: sentiment column if exists, else None
    "hashtags":       "hashtags",        # UPDATE: hashtags column if exists, else None
}

# Table name — UPDATE after schema extraction
POSTS_TABLE = "posts"   # most likely name; update after extraction


class MySQLConnector:
    def __init__(self):
        self.config = {
            "host":     settings.MYSQL_HOST,
            "user":     settings.MYSQL_USER,
            "password": settings.MYSQL_PASSWORD,
            "database": settings.MYSQL_DATABASE,
            "charset":  "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor,
            "connect_timeout": 10,
        }

    @contextmanager
    def get_connection(self):
        conn = pymysql.connect(**self.config)
        try:
            yield conn
        finally:
            conn.close()

    def get_new_records(self, since_id: int, batch_size: int = 500) -> list[dict]:
        """
        Fetch records with id > since_id (incremental pull).
        Returns normalized records ready for embedding.
        """
        c = COLUMN_MAP
        query = f"""
            SELECT
                `{c['post_id']}`        AS post_id,
                `{c['content']}`        AS content,
                `{c['platform']}`       AS platform,
                `{c['author']}`         AS author,
                `{c['language']}`       AS language,
                `{c['district']}`       AS district,
                `{c['created_at']}`     AS created_at,
                `{c['source_url']}`     AS source_url
            FROM `{POSTS_TABLE}`
            WHERE `{c['post_id']}` > %s
              AND `{c['content']}` IS NOT NULL
              AND `{c['content']}` != ''
            ORDER BY `{c['post_id']}` ASC
            LIMIT %s
        """
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (since_id, batch_size))
                rows = cursor.fetchall()
        return [dict(r) for r in rows]

    def get_max_id(self) -> int:
        """Get current maximum post_id in MySQL."""
        c = COLUMN_MAP
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT MAX(`{c['post_id']}`) AS max_id FROM `{POSTS_TABLE}`")
                row = cursor.fetchone()
                return row["max_id"] or 0

    def get_record_by_id(self, post_id: int) -> dict | None:
        """Fetch a single record for verification."""
        c = COLUMN_MAP
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"SELECT * FROM `{POSTS_TABLE}` WHERE `{c['post_id']}` = %s",
                    (post_id,)
                )
                row = cursor.fetchone()
                return dict(row) if row else None

    def test_connection(self) -> bool:
        """Verify VPN + DB connectivity."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
            logger.info("MySQL connection OK")
            return True
        except Exception as e:
            logger.error(f"MySQL connection FAILED: {e}")
            logger.error("Make sure ZeroTier VPN is connected to network: b6079f73c61bb152")
            return False
