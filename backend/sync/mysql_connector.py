"""
MySQL connector for up_police_matrix database.
Reads from three tables (in priority order):
  1. analyzed_data  — individual NLP-enriched posts (1.4M rows, growing at ~30k/day)
  2. topic          — AI-grouped incident topics (301k rows)
  3. district_internal_report — official police reports (1k rows, very high value)

Does NOT read post_bank (635M rows — raw feed, already absorbed into analyzed_data).
"""
import pymysql
import pymysql.cursors
from contextlib import contextmanager
from loguru import logger
from backend.config import settings


class MySQLConnector:
    def __init__(self):
        self.config = {
            "host":        settings.MYSQL_HOST,
            "user":        settings.MYSQL_USER,
            "password":    settings.MYSQL_PASSWORD,
            "database":    settings.MYSQL_DATABASE,
            "charset":     "utf8mb4",
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

    def test_connection(self) -> bool:
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            logger.info("MySQL connection OK")
            return True
        except Exception as e:
            logger.error(f"MySQL connection FAILED: {e}")
            return False

    # ─── analyzed_data (main post feed) ──────────────────────────────────────

    def get_analyzed_data(self, since_id: int, batch_size: int = 300) -> list[dict]:
        """
        Incremental pull from analyzed_data joined with topic for topic_title.
        Only fetches records with actual content.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        ad.id,
                        ad.post_bank_post_snippet      AS content,
                        ad.enhanced_text,
                        ad.contextual_understanding,
                        ad.incidents,
                        ad.post_bank_post_timestamp    AS occurred_at,
                        ad.post_bank_core_source       AS platform,
                        ad.post_bank_source            AS source_detail,
                        ad.post_bank_author_username   AS author,
                        ad.post_bank_author_name       AS author_name,
                        ad.detected_language           AS language,
                        ad.primary_district            AS district,
                        ad.primary_thana               AS thana,
                        ad.primary_location            AS location_str,
                        ad.broad_category              AS event_type,
                        ad.sub_category                AS sub_event_type,
                        ad.sentiment_label             AS sentiment,
                        ad.sentiment_confidence,
                        ad.person_names,
                        ad.organisation_names,
                        ad.district_names,
                        ad.hashtags,
                        ad.keywords_cloud,
                        ad.post_bank_post_url          AS source_url,
                        ad.emotional_primary_emotion   AS emotion,
                        ad.emotional_secondary_emotion AS emotion2,
                        ad.emotional_intensity,
                        ad.post_bank_likes             AS likes,
                        ad.post_bank_views             AS views,
                        ad.post_bank_retweets          AS retweets,
                        ad.created_at,
                        ad.unique_topic_id,
                        t.topic_title
                    FROM analyzed_data ad
                    LEFT JOIN topic t ON ad.unique_topic_id = t.unique_topic_id
                    WHERE ad.id > %s
                      AND ad.post_bank_post_snippet IS NOT NULL
                      AND ad.post_bank_post_snippet != ''
                    ORDER BY ad.id ASC
                    LIMIT %s
                """, (since_id, batch_size))
                return [dict(r) for r in cur.fetchall()]

    def get_analyzed_data_max_id(self) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(id) AS m FROM analyzed_data")
                row = cur.fetchone()
                return row["m"] or 0

    # ─── topic table ─────────────────────────────────────────────────────────

    def get_topics(self, since_id: int, batch_size: int = 200) -> list[dict]:
        """
        Pull grouped incident topics. These represent aggregated intelligence.
        High value — one topic covers many individual posts.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id,
                        unique_topic_id,
                        topic_title,
                        broad_category,
                        sub_category,
                        primary_districts,
                        primary_thana,
                        primary_location,
                        keywords_cloud,
                        hashtags,
                        command_center_description,
                        int_description,
                        total_no_of_post,
                        created_at,
                        updated_at,
                        topic_status
                    FROM topic
                    WHERE id > %s
                      AND topic_title IS NOT NULL
                    ORDER BY id ASC
                    LIMIT %s
                """, (since_id, batch_size))
                return [dict(r) for r in cur.fetchall()]

    def get_topics_max_id(self) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(id) AS m FROM topic")
                row = cur.fetchone()
                return row["m"] or 0

    def get_updated_topics(self, since_updated_at: str, limit: int = 200) -> list[dict]:
        """
        Fetch topics updated after a given datetime — for re-embedding updated topics.
        Topics get updated as new posts are added to them.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, unique_topic_id, topic_title, broad_category,
                           sub_category, primary_districts, keywords_cloud,
                           command_center_description, int_description,
                           total_no_of_post, updated_at, topic_status
                    FROM topic
                    WHERE updated_at > %s AND topic_title IS NOT NULL
                    ORDER BY updated_at ASC
                    LIMIT %s
                """, (since_updated_at, limit))
                return [dict(r) for r in cur.fetchall()]

    # ─── district_internal_report ─────────────────────────────────────────────

    def get_internal_reports(self, since_id: int, batch_size: int = 50) -> list[dict]:
        """
        Official police internal reports — very high credibility source.
        Small table (1k rows) but extremely high value for the AI bot.
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id,
                        district,
                        thana,
                        incident_date_time,
                        incident_description,
                        crime_type,
                        accused_names,
                        victim_name,
                        arrest_status,
                        final_remark,
                        headquater_remark,
                        dgp_remark,
                        unique_topic_id,
                        creation_date
                    FROM district_internal_report
                    WHERE id > %s
                      AND incident_description IS NOT NULL
                    ORDER BY id ASC
                    LIMIT %s
                """, (since_id, batch_size))
                return [dict(r) for r in cur.fetchall()]

    def get_internal_reports_max_id(self) -> int:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(id) AS m FROM district_internal_report")
                row = cur.fetchone()
                return row["m"] or 0
