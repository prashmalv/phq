"""
NLP Enrichment Pipeline
Processes raw social/news text through:
  1. Language detection
  2. Translation (Hindi → English if needed, keep both)
  3. Named Entity Recognition (persons, orgs, locations)
  4. Geo-tagging (district/city resolution for UP)
  5. Event classification
  6. Sentiment scoring
  7. Credibility scoring
"""
import re
from datetime import datetime
from typing import Optional
from uuid import uuid4

from langdetect import detect
from loguru import logger
from transformers import pipeline as hf_pipeline

from backend.config import settings

# ─── Event type keywords (Hindi + English) ───────────────────────────────────
EVENT_KEYWORDS: dict[str, list[str]] = {
    "violence": [
        "violence", "attack", "assault", "fight", "riot", "mob", "beat",
        "हिंसा", "मारपीट", "दंगा", "हमला", "लाठी", "पत्थरबाज़ी",
    ],
    "stampede": [
        "stampede", "crush", "crowd disaster", "trampled",
        "भगदड़", "भीड़ में हादसा", "कुचला",
    ],
    "protest": [
        "protest", "demonstration", "agitation", "dharna", "rally", "march",
        "विरोध", "प्रदर्शन", "धरना", "रैली", "आंदोलन",
    ],
    "accident": [
        "accident", "crash", "collision", "mishap", "boat accident",
        "दुर्घटना", "हादसा", "टक्कर", "नाव हादसा",
    ],
    "natural_disaster": [
        "flood", "earthquake", "landslide", "cyclone", "drought",
        "बाढ़", "भूकंप", "भूस्खलन", "सूखा",
    ],
    "misinformation": [
        "fake news", "rumor", "misinformation", "hoax", "false claim",
        "अफवाह", "फेक न्यूज़", "झूठी खबर",
    ],
    "fire": [
        "fire", "blaze", "arson", "explosion",
        "आग", "अग्निकांड", "विस्फोट",
    ],
    "crime": [
        "murder", "rape", "robbery", "theft", "kidnap", "abduction",
        "हत्या", "बलात्कार", "डकैती", "चोरी", "अपहरण",
    ],
}


class NLPPipeline:
    def __init__(self):
        logger.info("Loading NLP models...")
        # Multilingual NER (persons, orgs, locations)
        self._ner = hf_pipeline(
            "token-classification",
            model="xlm-roberta-large-finetuned-conll03-english",
            aggregation_strategy="simple",
        )
        # Multilingual sentiment
        self._sentiment = hf_pipeline(
            "sentiment-analysis",
            model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
            max_length=512,
            truncation=True,
        )
        self._district_map = self._build_district_map()
        logger.info("NLP models loaded")

    def _build_district_map(self) -> dict[str, str]:
        """Build a lookup: keyword → canonical district name."""
        mapping = {}
        for district in settings.UP_DISTRICTS:
            mapping[district.lower()] = district
            # Hindi transliterations / common variants
        # Add common aliases
        aliases = {
            "kashi": "Varanasi",
            "banaras": "Varanasi",
            "prayag": "Prayagraj",
            "allahabad": "Prayagraj",
            "kanpur": "Kanpur Nagar",
            "noida": "Gautam Buddha Nagar",
            "greater noida": "Gautam Buddha Nagar",
            "gbn": "Gautam Buddha Nagar",
        }
        mapping.update(aliases)
        return mapping

    # ─── Public entry point ─────────────────────────────────────────────────

    def enrich(self, raw: dict) -> dict:
        """
        Takes a raw event dict and returns an enriched event dict.
        raw must contain: content (str), source (str), occurred_at (datetime), source_url (str)
        """
        content = raw.get("content", "")
        if not content:
            return raw

        language = self._detect_language(content)
        content_en = content  # keep original; translate if needed for NER

        entities = self._extract_entities(content_en)
        district, city = self._resolve_location(content, entities)
        event_type = self._classify_event(content)
        sentiment, sentiment_score = self._score_sentiment(content)
        credibility = self._score_credibility(raw)
        tags = self._extract_tags(content)

        return {
            "event_id": raw.get("event_id", uuid4()),
            "source": raw.get("source"),
            "source_url": raw.get("source_url"),
            "content": content,
            "content_hi": raw.get("content_hi"),
            "author_handle": raw.get("author_handle"),
            "author_verified": raw.get("author_verified", False),
            "language": language,
            "event_type": event_type,
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "credibility": credibility,
            "district": district,
            "tehsil": raw.get("tehsil"),
            "city": city,
            "state": "Uttar Pradesh",
            "lat": raw.get("lat"),
            "lon": raw.get("lon"),
            "tags": tags,
            "entities": entities,
            "raw_data": raw.get("raw_data", {}),
            "occurred_at": raw.get("occurred_at", datetime.utcnow()),
        }

    # ─── Language detection ─────────────────────────────────────────────────

    def _detect_language(self, text: str) -> str:
        try:
            lang = detect(text[:500])
            return lang
        except Exception:
            return "unknown"

    # ─── NER ────────────────────────────────────────────────────────────────

    def _extract_entities(self, text: str) -> dict:
        persons, orgs, locations = [], [], []
        try:
            results = self._ner(text[:512])
            for r in results:
                label = r["entity_group"]
                word = r["word"].strip()
                if not word or len(word) < 2:
                    continue
                if label == "PER":
                    persons.append(word)
                elif label == "ORG":
                    orgs.append(word)
                elif label == "LOC":
                    locations.append(word)
        except Exception as e:
            logger.warning(f"NER failed: {e}")

        return {
            "persons": list(set(persons)),
            "orgs": list(set(orgs)),
            "locations": list(set(locations)),
        }

    # ─── Geo-tagging ────────────────────────────────────────────────────────

    def _resolve_location(self, text: str, entities: dict) -> tuple[Optional[str], Optional[str]]:
        text_lower = text.lower()
        # First check NER-extracted locations
        for loc in entities.get("locations", []):
            canonical = self._district_map.get(loc.lower())
            if canonical:
                return canonical, loc

        # Then scan full text
        for keyword, canonical in self._district_map.items():
            if keyword in text_lower:
                return canonical, None

        return None, None

    # ─── Event classification ────────────────────────────────────────────────

    def _classify_event(self, text: str) -> str:
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for event_type, keywords in EVENT_KEYWORDS.items():
            hit = sum(1 for kw in keywords if kw.lower() in text_lower)
            if hit:
                scores[event_type] = hit
        if not scores:
            return "general"
        return max(scores, key=scores.__getitem__)

    # ─── Sentiment ──────────────────────────────────────────────────────────

    def _score_sentiment(self, text: str) -> tuple[int, float]:
        try:
            result = self._sentiment(text[:512])[0]
            label = result["label"].lower()
            score = result["score"]
            if "positive" in label:
                return 1, score
            elif "negative" in label:
                return -1, -score
            else:
                return 0, 0.0
        except Exception as e:
            logger.warning(f"Sentiment scoring failed: {e}")
            return 0, 0.0

    # ─── Credibility ────────────────────────────────────────────────────────

    def _score_credibility(self, raw: dict) -> float:
        score = 0.5
        source = raw.get("source", "")
        if source in ("news", "govt", "fir"):
            score = 0.9
        elif raw.get("author_verified"):
            score = 0.75
        elif source == "twitter":
            score = 0.5
        elif source in ("facebook", "instagram"):
            score = 0.4
        return score

    # ─── Tag extraction ─────────────────────────────────────────────────────

    def _extract_tags(self, text: str) -> list[str]:
        hashtags = re.findall(r"#(\w+)", text)
        return [t.lower() for t in hashtags]
