"""
Matrix AI Sahayak — Local Demo Runner
=======================================
Starts a mock server on http://localhost:8000 with pre-loaded Smart Meter
incident data. No MySQL, Qdrant, or LLM required.

Usage:
  cd /path/to/PHQ
  ./demo.sh
"""
import json
import os
import re as _re
import sys
import threading
import time
import urllib.request
import uuid
import webbrowser
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# ─── Make sure FastAPI / uvicorn are importable ───────────────────────────────
try:
    import uvicorn
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
except ImportError:
    print("Installing dependencies...")
    os.system(f"{sys.executable} -m pip install fastapi uvicorn[standard] -q")
    import uvicorn
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).parent.parent

# ─── Mock data (based on Smart Meter Agitation, Apr-May 2026) ─────────────────

MOCK_ANSWERS = {
    "smart meter": {
        "answer": """Smart Meter Agitation — UP (28 Apr – 4 May 2026) के बारे में:

**773 कुल पोस्ट** इस 7-दिवसीय अवधि में दर्ज किए गए, जो मुख्यतः Twitter/X (96.4%) पर थे।

**प्रमुख घटनाएं:**
- 30 अप्रैल: फिरोजाबाद में महिलाओं ने सड़क जाम किया
- 01 मई: आगरा/कागरौल में ग्रामीणों ने मीटर उखाड़े — 16 नामजद + 500-600 पर FIR [1]
- 03 मई: सर्वाधिक Spike (302 posts) — AAP का राज्यव्यापी विरोध, लखनऊ में शक्ति भवन घेराव [2]

**Sentiment:** 87.3% नकारात्मक | 'Smart Cheater' और 'Smart Loot' slogans viral

**Most Active Districts:** Agra (195 mentions) → Lucknow (152) → Firozabad (95) [3]""",
        "confidence": 0.89,
        "evidence_count": 12,
        "sources": ["Twitter", "Facebook", "Official Report"],
        "district_detected": None,
        "latency_ms": 1180,
    },
    "agra": {
        "answer": """**आगरा जिला — Smart Meter Protest:**

आगरा इस विरोध का मुख्य केंद्र रहा — कुल **195 उल्लेख**, जो पूरे UP में सर्वाधिक था।

**01 मई 2026 — कागरौल घटना [1]:**
- ग्रामीणों ने Smart Meter उखाड़कर विद्युत उपकेंद्र पर फेंके
- विद्युत विभाग ने 16 व्यक्तियों को नामजद किया
- 500-600 अज्ञात ग्रामीणों पर FIR दर्ज
- यह खबर 02 मई को @bstvlive और @AHindinews ने वायरल की [2]

**Spike Analysis:**
- 01 मई: 68 posts (आगरा-specific) — FIR के बाद
- 02 मई: 57 posts — FIR की खबर फैलने पर
- Sentiment: अत्यंत नकारात्मक

**Law & Order Status:** FIR active, ग्रामीण असंतोष बरकरार [3]""",
        "confidence": 0.92,
        "evidence_count": 8,
        "sources": ["Twitter", "Official Report"],
        "district_detected": "Agra",
        "latency_ms": 980,
    },
    "lucknow": {
        "answer": """**लखनऊ — Smart Meter Protest (152 उल्लेख):**

**03 मई 2026 — शक्ति भवन घेराव [1]:**
- AAP ने शक्ति भवन (विद्युत विभाग मुख्यालय) का घेराव किया
- पुलिस से 'नोकझोंक' और अस्थायी हिरासत
- @SanjayAzadSln (22 लाख followers) ने lead किया अभियान

**Daily Pattern:**
- 28 Apr: 14 posts | 29 Apr: 20 posts | 30 Apr: 5 posts
- 01 May: 1 post | 02 May: 1 post | **03 May: 58 posts** (Spike)

**Narrative:** BJP/Yogi सरकार को directly target करने वाले posts सर्वाधिक [2]

Confidence: High — 7 verified accounts tracked""",
        "confidence": 0.88,
        "evidence_count": 6,
        "sources": ["Twitter"],
        "district_detected": "Lucknow",
        "latency_ms": 1050,
    },
    "sentiment": {
        "answer": """**Smart Meter Protest — Sentiment Analysis:**

| Sentiment | Posts | % |
|-----------|-------|---|
| Negative (नकारात्मक) | 675 | **87.3%** |
| Neutral (तटस्थ) | 96 | 12.4% |
| Positive (सकारात्मक) | 2 | 0.3% |

**Dominant Emotions [1]:**
- Outrage (आक्रोश): बहुत अधिक — मीटर उखाड़ना, FIR का विरोध
- Dissatisfaction (असंतोष): बहुत अधिक — बढ़े हुए बिजली बिल
- Fear (भय): मध्यम — FIR, गिरफ्तारी का डर

**Key Phrases going viral [2]:** 'Smart Cheater', 'Smart Loot', 'Sarkari Loot'

**Emerging Risk:** Rakesh Tikait (@RakeshTikaitBKU) की संभावित entry — किसान वर्ग की भागीदारी का संकेत""",
        "confidence": 0.85,
        "evidence_count": 9,
        "sources": ["Twitter", "Facebook"],
        "district_detected": None,
        "latency_ms": 1320,
    },
    "aap": {
        "answer": """**AAP की भूमिका — Smart Meter Protest:**

AAP ने **25.1%** (194 posts) कंटेंट उत्पन्न किया — यह एक **सुनियोजित राजनीतिक अभियान** का संकेत है [1]।

**Coordinated Activity — 03 मई 21:56-21:57 (1 मिनट में):**
@AAPUttarPradesh, @SakshiGupta_AAP, @VikasSlnAAP, @aapvijayanand
— चारों ने एक ही message साझा किया [2]

**Key AAP Handles:**
- @SanjayAzadSln — 22 लाख followers — लखनऊ शक्ति भवन अभियान
- @AAPUttarPradesh — 1.85 लाख followers — राज्यव्यापी coordination

**Political Framing:** इस मुद्दे को 2027 विधानसभा चुनाव से जोड़ा जा रहा है [3]

Note: यह Coordinated Political Campaign है, Coordinated Inauthentic Behavior (Bot activity) नहीं""",
        "confidence": 0.91,
        "evidence_count": 11,
        "sources": ["Twitter"],
        "district_detected": None,
        "latency_ms": 1090,
    },

    "mathura": {
        "answer": """**मथुरा जिला — Social Media Intelligence (पिछले 30 दिन)**

**कुल पोस्ट:** 312 | मुख्य Platform: Twitter/X (78%), Facebook (18%)

**प्रमुख Topics:**
- शाही ईदगाह legal proceedings update — 45 posts (largely informational, no inflammatory content)
- Kawad Yatra route preparation — positive coordination posts, 67 mentions
- Braj Mandal Parikrama security — 38 posts, सकारात्मक

**Sentiment Distribution:**
| Sentiment | Posts | % |
|-----------|-------|---|
| Positive (भक्ति/धार्मिक) | 194 | 62.2% |
| Neutral | 87 | 27.9% |
| Negative | 31 | 9.9% |

**Law & Order:** कोई major incident नहीं। Yatra season approaching — monitoring बढ़ाएं।
**Alert Level:** 🟡 Medium — Elevated monitoring during religious events recommended""",
        "confidence": 0.83,
        "evidence_count": 9,
        "sources": ["Twitter", "Facebook"],
        "latency_ms": 960,
    },

    "varanasi": {
        "answer": """**वाराणसी जिला — Social Media Intelligence (पिछले 30 दिन)**

**कुल पोस्ट:** 478 | Kashi Vishwanath Corridor impact — sustained high activity

**Positive Trends:**
- International tourists से Ghat experience posts — 142 posts, viral reach
- CM Office Kashi event announcements — 89 shares, positive
- Dev Deepawali preparation — early coordination posts increasing

**Monitoring Points:**
- Dashashwamedh area traffic disruption — 31 posts (crowd management)
- Boat घाट dispute (minor) — 18 posts, local, resolved
- ₹400 prasad scam viral claim — 24 posts, fact-check needed ★

**Platform-wise:**
- Twitter: 52% | Instagram: 28% | Facebook: 20%

**Sentiment:** 71% positive, 22% neutral, 7% negative (logistics only)
**Alert Level:** 🟢 Normal — Tourism volume high, no L&O concerns""",
        "confidence": 0.87,
        "evidence_count": 11,
        "sources": ["Twitter", "Instagram", "Facebook"],
        "latency_ms": 1020,
    },

    "kanpur": {
        "answer": """**कानपुर जिला — Social Media Intelligence (पिछले 15 दिन)**

**कुल पोस्ट:** 241

**⚠️ Watch: Labour Unrest — Panki Industrial Area**
- 67 posts: Textile unit workers — delayed salary payments
- Key handles: @KanpurMazdoorSangh (8.2K followers)
- Sentiment: Angry but non-violent; potential for escalation

**Smart Meter Connection:**
- 72 Kanpur posts linked to UP Smart Meter agitation
- AAP handles coordinating from Kanpur — @VikasKanpurAAP active

**Communal Harmony:**
- No inflammatory content detected (7-day scan)
- Inter-community Iftar/events covered positively

**Sentiment:** 61% negative (economic), 32% neutral, 7% positive
**Recommendations:**
- Monitor Panki area for wage-related escalation
- Watch AAP coordination ahead of potential Kanpur rally""",
        "confidence": 0.80,
        "evidence_count": 10,
        "sources": ["Twitter", "Facebook", "Official Report"],
        "latency_ms": 1100,
    },

    "kawad": {
        "answer": """**Kawad Yatra 2026 — Pre-Event Social Media Analysis**

**यात्रा Period:** July 2026 (expected) | **Monitoring Start:** Now

**Current Social Media Activity (1,240 posts, last 7 days):**
- Hashtags trending: #KawadYatra2026, #BolBam, #Haridwar
- Devotee groups organizing — Meerut, Muzaffarnagar, Hapur corridors

**Route Risk Assessment:**
| District | Activity | Risk |
|----------|----------|------|
| Meerut | 312 posts | 🟡 Medium |
| Muzaffarnagar | 198 posts | 🟡 Medium |
| Hapur | 145 posts | 🟢 Low |
| Bulandshahr | 89 posts | 🟢 Low |

**Historical Context:** 2024 mein Muzaffarnagar bypass pe minor crowd incident — social media coordination gap था।

**Recommendations:**
- Deploy real-time social media monitoring along route
- Pre-position forces at high-activity nodes
- Counter-narrative readiness for misinformation

**Sentiment:** 78% positive (devotion), 15% neutral, 7% concern (crowd/traffic)""",
        "confidence": 0.88,
        "evidence_count": 14,
        "sources": ["Twitter", "Facebook", "WhatsApp Intel"],
        "latency_ms": 1250,
    },

    "ayodhya": {
        "answer": """**अयोध्या जिला — Social Media Intelligence (पिछले 7 दिन)**

**Ram Mandir Post-Inauguration — Ongoing High Activity**

**Visitor Volume Impact:**
- 3,450+ posts | 2.8 lakh+ daily visitors
- Instagram reels from Mandir — 1.2M+ cumulative views this week

**Minor Concerns (Non-L&O):**
- Hotel/accommodation scarcity complaints — 89 posts
- Prasadam queue wait time complaints — 67 posts
- Parking/traffic near Sarayu Ghat — 44 posts (local issue)

**Political Activity:**
- Opposition posts on "commercialization" — 34 posts, minimal traction
- No inflammatory content detected

**Upcoming Monitoring:**
- Ram Navami preparation posts starting — crowd surge expected
- VIP visit rumors circulating — verification needed

**Sentiment:** 84% positive, 14% neutral, 2% negative (logistics only)
**Alert Level:** 🟢 Normal — High tourism, zero security concerns""",
        "confidence": 0.91,
        "evidence_count": 16,
        "sources": ["Twitter", "Instagram", "Facebook"],
        "latency_ms": 980,
    },

    "gorakhpur": {
        "answer": """**गोरखपुर जिला — Social Media Intelligence (पिछले 15 दिन)**

**कुल पोस्ट:** 189 | CM का गृह जिला — always elevated monitoring

**Key Narratives:**
- CM Yogi health facility launch — 78 posts, positive coverage
- Gorakhpur-Lucknow Expressway inauguration post — 45 shares
- Gorakhnath Temple events — 34 posts, peaceful

**⚠️ Emerging Issue:**
- Industrial area noise pollution complaints — 23 posts, local residents
- Ramgarh Tal development delay posts — 19 posts, frustration visible

**Anti-Establishment Posts:**
- 31 posts criticizing municipal administration (garbage, roads)
- Handled by @GorakhpurMayor account — responsive, contained

**Sentiment:** 58% positive (CM coverage), 27% neutral, 15% negative (local admin)
**Alert Level:** 🟢 Normal""",
        "confidence": 0.79,
        "evidence_count": 8,
        "sources": ["Twitter", "Facebook"],
        "latency_ms": 890,
    },

    "meerut": {
        "answer": """**मेरठ जिला — Social Media Intelligence (पिछले 15 दिन)**

**कुल पोस्ट:** 267 | Western UP hub — sensitive district

**Kawad Yatra Corridor:**
- 145 posts about route preparation — mostly coordination
- NH-58 diversion announcement — mixed response (67 negative from truck drivers)

**⚠️ Watch: Communal Harmony Monitor**
- 18 posts with communal undertone detected (last 7 days)
- Source: 3 accounts with <500 followers, low reach
- Content: Isolated, not coordinated — standard monitoring sufficient

**Economic Issues:**
- Sports goods industry slowdown posts — 34 posts
- Worker welfare demands — 23 posts, peaceful

**Positive:**
- Inter-community cricket tournament — viral positive content

**Sentiment:** 52% neutral, 31% negative (traffic/economy), 17% positive
**Alert Level:** 🟡 Medium — Kawad corridor + communal watch""",
        "confidence": 0.81,
        "evidence_count": 11,
        "sources": ["Twitter", "Facebook", "Official Report"],
        "latency_ms": 1080,
    },

    "protest": {
        "answer": """**UP — Active Protest Monitoring Dashboard (May 2026)**

**Currently Active Agitations:**

| Issue | Districts | Posts | Intensity |
|-------|-----------|-------|-----------|
| Smart Meter | 32 districts | 773 | 🔴 High |
| Labour (Kanpur textile) | Kanpur | 67 | 🟡 Medium |
| Agricultural land acquisition | Mathura, Agra | 45 | 🟡 Medium |
| Road condition | Gorakhpur, Meerut | 38 | 🟢 Low |

**Trending Hashtags (Last 48 Hours):**
- #SmartMeterVirodh — 445 tweets
- #UPBijliScam — 312 tweets
- #KisanAdhikar — 89 tweets

**Key Risk Districts:** Agra, Lucknow, Firozabad, Kanpur

**Political Amplification:**
- AAP: 194 posts (25.1% of Smart Meter content)
- SP handles: 67 posts
- BJP counter-narrative: 34 posts

**Recommendation:** Agra FIR on 500+ villagers continues to fuel negative narrative — consider partial withdrawal or communication strategy.""",
        "confidence": 0.86,
        "evidence_count": 13,
        "sources": ["Twitter", "Facebook", "Official Report"],
        "latency_ms": 1180,
    },
}

# ─── Live news fetcher ────────────────────────────────────────────────────────
# Multiple RSS sources tried in order; first one to return items wins.
# Google News blocks cloud server IPs, so we use NDTV / TOI / IndiaTVNews first.

_news_cache: dict = {"items": [], "fetched_at": None}
_NEWS_TTL = 1800  # 30-minute cache

_RSS_SOURCES = [
    # (label, url)
    ("NDTV",          "https://feeds.feedburner.com/ndtvnews-india-news"),
    ("Times of India","https://timesofindia.indiatimes.com/rssfeeds/296589292.cms"),
    ("India TV",      "https://www.indiatvnews.com/rssnews/india.xml"),
    ("Hindustan Times","https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml"),
    # Google News as last-resort (may be blocked on some cloud IPs)
    ("Google News",
     "https://news.google.com/rss/search?q=uttar+pradesh+police&hl=en-IN&gl=IN&ceid=IN:en"),
]

_UP_KEYWORDS = {
    "uttar pradesh", "up police", "lucknow", "agra", "varanasi", "kanpur",
    "mathura", "firozabad", "allahabad", "prayagraj", "meerut", "noida",
    "ghaziabad", "bareilly", "gorakhpur", "law order", "protest", "agitation",
    "fir", "arrest", "crime", "incident",
}


def _strip_html(text: str) -> str:
    return _re.sub(r"<[^>]+>", "", text or "").strip()


def _fetch_rss(url: str, label: str, max_items: int = 8) -> list[dict]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    with urllib.request.urlopen(req, timeout=8) as resp:
        root = ET.fromstring(resp.read())
    items = []
    for item in root.findall(".//item")[:max_items]:
        title = _strip_html(item.findtext("title", ""))
        desc  = _strip_html(item.findtext("description", ""))[:300]
        pub   = (item.findtext("pubDate", "") or "")[:22]
        if title:
            items.append({"title": title, "description": desc,
                          "pub_date": pub, "source": label})
    return items


def _fetch_up_news() -> list[dict]:
    now = datetime.utcnow()
    if (
        _news_cache["fetched_at"]
        and (now - _news_cache["fetched_at"]).seconds < _NEWS_TTL
        and _news_cache["items"]
    ):
        return _news_cache["items"]

    all_items: list[dict] = []
    for label, url in _RSS_SOURCES:
        try:
            fetched = _fetch_rss(url, label)
            # Keep only India/UP relevant items from national feeds
            relevant = [
                it for it in fetched
                if any(kw in (it["title"] + it["description"]).lower()
                       for kw in _UP_KEYWORDS)
            ]
            all_items.extend(relevant or fetched[:3])  # fallback: take top 3 anyway
            print(f"  [news] {label}: {len(fetched)} fetched, {len(relevant)} UP-relevant")
            if len(all_items) >= 10:
                break
        except Exception as e:
            print(f"  [news] {label}: {e}")

    _news_cache["items"] = all_items[:15]
    _news_cache["fetched_at"] = now
    return _news_cache["items"]


_UP_CITIES = [
    "lucknow", "agra", "varanasi", "kanpur", "mathura", "meerut", "noida",
    "ghaziabad", "allahabad", "prayagraj", "gorakhpur", "bareilly", "aligarh",
    "moradabad", "firozabad", "ayodhya", "faizabad", "muzaffarnagar", "hapur",
    "bulandshahr", "etah", "mainpuri", "jhansi", "banda",
]

_TOPIC_KEYWORDS = {
    "protest": ["protest", "agitation", "demonstration", "dharna", "virodh", "andolan"],
    "crime":   ["crime", "murder", "robbery", "theft", "fir", "arrest", "accused"],
    "communal":["communal", "riot", "tension", "violence", "hindu", "muslim", "church"],
    "traffic": ["traffic", "jam", "accident", "highway", "road", "expressway"],
    "political":["election", "bjp", "sp", "bsp", "aap", "congress", "rally", "campaign"],
    "law":     ["law", "order", "police", "encounter", "security", "deployment"],
}


def _news_response(query: str) -> dict:
    all_news = _fetch_up_news()
    q = query.lower()

    # Extract city and topic signals from query
    detected_cities  = [c for c in _UP_CITIES if c in q]
    detected_topics  = [t for t, kws in _TOPIC_KEYWORDS.items() if any(k in q for k in kws)]
    q_words = {w for w in q.split() if len(w) > 3}

    def _score(item: dict) -> int:
        text = (item["title"] + " " + item["description"]).lower()
        score = 0
        # City match → strong signal
        score += sum(3 for c in detected_cities if c in text)
        # Topic match → medium signal
        score += sum(2 for t in detected_topics
                     for kw in _TOPIC_KEYWORDS[t] if kw in text)
        # Generic word overlap
        score += sum(1 for w in q_words if w in text)
        return score

    scored = [(it, _score(it)) for it in all_news]
    scored.sort(key=lambda x: -x[1])
    hits = [it for it, sc in scored if sc > 0][:5]

    # Fallback: if nothing matched, show recent UP news anyway
    if not hits and all_news:
        hits = all_news[:4]

    if hits:
        city_str  = " / ".join(c.title() for c in detected_cities) if detected_cities else "Uttar Pradesh"
        topic_str = " + ".join(detected_topics) if detected_topics else "general"
        lines = [
            f"**Live News — {city_str} ({topic_str}) — हाल की खबरें:**\n",
            "---",
        ]
        for i, it in enumerate(hits, 1):
            lines.append(f"**{i}. {it['title']}**")
            if it["description"]:
                lines.append(it["description"])
            if it["pub_date"]:
                lines.append(f"*{it['source']} · {it['pub_date']}*")
            lines.append("")
        lines += [
            "---",
            f"*Query context detected: city={city_str}, topic={topic_str}. "
            "Production mein यही query 14 लाख+ MySQL social media records से "
            "match होकर detailed intelligence देगा।*",
        ]
        return {
            "answer": "\n".join(lines),
            "confidence": 0.70,
            "evidence_count": len(hits),
            "sources": list({it["source"] for it in hits}),
            "latency_ms": 1200,
        }

    return {
        "answer": (
            f'**Query:** "{query}"\n\n'
            "Live news feed abhi available nahi hai।\n\n"
            "**Demo ke liye ye queries try karein:**\n"
            "• Smart meter protest, Agra, Lucknow, Mathura, Varanasi\n"
            "• Kanpur, Gorakhpur, Meerut, Ayodhya, Kawad Yatra\n"
            "• Sentiment analysis, Protest dashboard, AAP campaign\n\n"
            "*Production mein 14 lakh+ real records se instant answer milega।*"
        ),
        "confidence": 0.3,
        "evidence_count": 0,
        "sources": ["Demo Mode"],
        "latency_ms": 300,
    }


# ─── In-memory session store ───────────────────────────────────────────────────
# { session_id: { "title": str, "messages": [...], "updated_at": str } }
_sessions: dict = {}


def _make_session_id() -> str:
    return f"demo-{uuid.uuid4().hex[:8]}"


def _store_turn(session_id: str, query: str, response: dict):
    now = datetime.utcnow().isoformat()
    if session_id not in _sessions:
        _sessions[session_id] = {
            "title": query[:60].strip(),
            "messages": [],
            "updated_at": now,
        }
    sess = _sessions[session_id]
    sess["messages"].append({"role": "user", "content": query, "meta": None})
    sess["messages"].append({
        "role": "assistant",
        "content": response["answer"],
        "meta": {
            "confidence": response["confidence"],
            "evidence_count": response["evidence_count"],
            "sources": response["sources"],
            "latency_ms": response["latency_ms"],
        },
    })
    sess["updated_at"] = datetime.utcnow().isoformat()


# ─── FastAPI Demo App ──────────────────────────────────────────────────────────

app = FastAPI(title="Matrix AI Sahayak — Demo Mode", docs_url="/api/docs")

_dedicated = ROOT / "frontend" / "dedicated"
_widget    = ROOT / "frontend" / "widget"
_logo      = ROOT / "frontend" / "logo"
if _dedicated.exists():
    app.mount("/static/app", StaticFiles(directory=str(_dedicated)), name="app")
if _widget.exists():
    app.mount("/static/widget", StaticFiles(directory=str(_widget)), name="widget")
if _logo.exists():
    app.mount("/static/logo", StaticFiles(directory=str(_logo)), name="logo")


def _match_query(query: str) -> dict | None:
    q = query.lower()
    for keyword, response in MOCK_ANSWERS.items():
        if keyword in q:
            return response
    return None  # caller should fall back to live news


@app.get("/", response_class=HTMLResponse)
@app.get("/ai-bot/", response_class=HTMLResponse)
async def serve_chat():
    index = _dedicated / "index.html"
    if index.exists():
        content = index.read_text()
        # Fix static paths
        ts = int(time.time())  # cache-buster so browser never loads stale app.js
        content = content.replace('href="app.css"', f'href="/static/app/app.css?v={ts}"')
        content = content.replace('src="app.js"',   f'src="/static/app/app.js?v={ts}"')
        # Inject demo config — sets DEMO_ANSWERS (new app.js) + PHQ_API_BASE (fallback)
        answers_json = json.dumps({k: {
            "answer": v["answer"], "confidence": v["confidence"],
            "evidence_count": v["evidence_count"], "sources": v["sources"],
            "latency_ms": v["latency_ms"],
        } for k, v in MOCK_ANSWERS.items()}, ensure_ascii=False)
        inject = (
            '<script>'
            # Always point to same origin — works on localhost AND Railway/Render
            'window.PHQ_API_BASE=window.location.origin;'
            f'window.DEMO_ANSWERS={answers_json};'
            '</script>'
        )
        content = content.replace('</head>', inject + '</head>')
        banner = (
            '<div style="background:#d97706;color:#fff;text-align:center;'
            'padding:7px 12px;font-size:12.5px;font-weight:500;">'
            '🎯 DEMO MODE — Smart Meter Agitation data (Apr–May 2026). '
            'Production connects to live MySQL.</div>'
        )
        content = content.replace("<body>", f"<body>{banner}")
        return HTMLResponse(content, headers={"Cache-Control": "no-store"})
    return HTMLResponse("<h2>Matrix AI Sahayak — Demo Mode</h2>"
                        "<p>Run from repo root: <code>./demo.sh</code></p>")


@app.post("/api/v2/chat/query")
async def chat_query(
    request: dict,
    authorization: str = Header(default="Bearer demo"),
):
    import asyncio
    query = request.get("query", "")
    session_id = request.get("session_id") or None

    if not session_id or session_id not in _sessions:
        session_id = _make_session_id()

    # Known topic → instant static answer; unknown → live news fetch
    response = _match_query(query)
    if response is None:
        response = await asyncio.to_thread(_news_response, query)

    _store_turn(session_id, query, response)
    return {"session_id": session_id, **response}


@app.get("/api/v2/chat/sessions")
async def list_sessions(authorization: str = Header(default="Bearer demo")):
    sessions = [
        {"session_id": sid, "title": s["title"], "updated_at": s["updated_at"]}
        for sid, s in _sessions.items()
    ]
    return sorted(sessions, key=lambda x: x["updated_at"], reverse=True)


@app.get("/api/v2/chat/sessions/{session_id}/messages")
async def get_session(session_id: str, authorization: str = Header(default="Bearer demo")):
    if session_id not in _sessions:
        return []
    sess = _sessions[session_id]
    return [
        {
            "role": m["role"],
            "content": m["content"],
            "meta": m.get("meta"),
            "created_at": sess["updated_at"],
        }
        for m in sess["messages"]
    ]


@app.get("/api/v2/reports/")
async def list_reports(authorization: str = Header(default="Bearer demo")):
    return [{"report_id": "RPT-DEMO", "title": "Smart Meter Agitation — UP (28 Apr – 04 May 2026)", "from_date": "2026-04-28", "to_date": "2026-05-04", "status": "completed", "trigger": "demo", "created_at": datetime.utcnow().isoformat()}]


@app.get("/api/v2/reports/RPT-DEMO/html", response_class=HTMLResponse)
async def demo_report(authorization: str = Header(default="Bearer demo")):
    report_path = ROOT / "docs" / "sample_report.html"
    if report_path.exists():
        return HTMLResponse(report_path.read_text())
    return HTMLResponse(_generate_inline_sample_report())


@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": "DEMO", "version": "1.0.0"}


def _generate_inline_sample_report() -> str:
    return """<!DOCTYPE html><html lang="hi"><head><meta charset="UTF-8"/>
<title>Sample Intelligence Report — Matrix AI Sahayak</title>
<style>
body{font-family:Arial,sans-serif;max-width:1000px;margin:0 auto;padding:20px;color:#1a1a1a}
.h{background:#1a3a6b;color:#fff;padding:24px;text-align:center}
.h h1{margin:0;font-size:20px;letter-spacing:1px}
.h p{margin:5px 0 0;font-size:13px;opacity:.85}
.s{background:#1e4d8c;color:#fff;padding:8px 14px;font-weight:bold;margin-top:18px}
table{width:100%;border-collapse:collapse;margin:10px 0}
th{background:#1e4d8c;color:#fff;padding:7px 10px;text-align:left}
td{padding:6px 10px;border-bottom:1px solid #e5e7eb}
tr:nth-child(even){background:#f9fafb}
.box{background:#eff6ff;border-left:4px solid #1e4d8c;padding:10px;margin:8px 0}
.kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}
.kpi{background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:12px;text-align:center}
.kpi-val{font-size:26px;font-weight:bold;color:#1e4d8c}
.kpi-label{font-size:11px;color:#6b7280;margin-top:2px}
.print-btn{display:inline-flex;align-items:center;gap:6px;background:#1e4d8c;color:#fff;
  border:none;padding:9px 18px;border-radius:6px;font-size:13px;cursor:pointer;font-weight:600}
.print-btn:hover{background:#1a3a6b}
.print-bar{text-align:right;margin-bottom:12px}
@media print{.print-bar{display:none}}
</style></head><body>
<div class="h">
  <h1>Social Media Intelligence Report</h1>
  <p>Issue: Smart Meter Agitation — Uttar Pradesh</p>
  <p>Reporting Period: 28 April 2026 – 04 May 2026</p>
  <p style="font-size:11px;margin-top:6px;opacity:.7">CONFIDENTIAL — For Senior Officers Only | Matrix AI Sahayak</p>
</div>
<div class="print-bar">
  <button class="print-btn" onclick="window.print()">🖨️ Print / Save as PDF</button>
</div>
<div class="kpi-grid">
<div class="kpi"><div class="kpi-val">773</div><div class="kpi-label">कुल पोस्ट/उल्लेख</div></div>
<div class="kpi"><div class="kpi-val" style="color:#dc2626">87.3%</div><div class="kpi-label">नकारात्मक भावना</div></div>
<div class="kpi"><div class="kpi-val">302</div><div class="kpi-label">Peak Day (03 May)</div></div>
<div class="kpi"><div class="kpi-val">32</div><div class="kpi-label">प्रभावित जिले</div></div>
</div>
<div class="s">SECTION 1 — Brief Summary</div>
<div class="box"><p>उत्तर प्रदेश में प्रीपेड Smart बिजली मीटर लगाने की सरकारी योजना के विरोध में 28 अप्रैल 2026 से 4 मई 2026 तक सोशल मीडिया पर एक बड़ा डिजिटल आंदोलन देखा गया। इस पूरे सप्ताह में कुल 773 पोस्ट/उल्लेख दर्ज किए गए।</p></div>
<div class="s">SECTION 2 — Activity Pattern</div>
<table><tr><th>तारीख</th><th>पोस्ट</th><th>मुख्य घटना</th></tr>
<tr><td>28 अप्रैल</td><td>68</td><td>आगरा, लखनऊ में प्रारंभिक विरोध</td></tr>
<tr><td>29 अप्रैल</td><td>54</td><td>मुरादाबाद, अलीगढ़ से आवाजें</td></tr>
<tr><td>30 अप्रैल</td><td>117</td><td>फिरोजाबाद — महिलाओं ने सड़क जाम किया</td></tr>
<tr><td>01 मई</td><td>100</td><td>आगरा FIR — 16 नामजद + 500-600 पर FIR</td></tr>
<tr><td>02 मई</td><td>120</td><td>FIR की खबर वायरल, मीडिया कवरेज</td></tr>
<tr><td>03 मई</td><td style="color:#dc2626;font-weight:bold">302</td><td>AAP राज्यव्यापी विरोध — Climax</td></tr>
<tr><td>04 मई</td><td>12</td><td>आंशिक दिन</td></tr>
<tr style="background:#1e4d8c;color:#fff"><td><b>Total</b></td><td><b>773</b></td><td></td></tr></table>
<div class="s">SECTION 5 — Geographic Analysis (Top 5)</div>
<table><tr><th>जिला</th><th>Mentions</th><th>मुख्य घटना</th></tr>
<tr><td>आगरा</td><td>195</td><td>कागरौल FIR — 16 नामजद + 500-600 अज्ञात</td></tr>
<tr><td>लखनऊ</td><td>152</td><td>शक्ति भवन AAP घेराव</td></tr>
<tr><td>फिरोजाबाद</td><td>95</td><td>महिला सड़क जाम</td></tr>
<tr><td>कानपुर</td><td>72</td><td>AAP और स्थानीय विरोध</td></tr>
<tr><td>फतेहपुर</td><td>49</td><td>मीटर उखाड़कर बिजलीघर में फेंके</td></tr></table>
<div class="s">SECTION 13 — Recommendations</div>
<div style="background:#f0fdf4;border-left:4px solid #22c55e;padding:10px;margin:8px 0">
<ul style="list-style:none;padding:0">
<li style="margin:6px 0">• आगरा FIR की समीक्षा — 500-600 अज्ञात ग्रामीणों पर FIR का narrative बेहद नकारात्मक</li>
<li style="margin:6px 0">• UPPCL की ओर से fact-based counter-narrative — 'Smart Meter से बिल कम होता है'</li>
<li style="margin:6px 0">• Grievance helpline prominently promote करें — Twitter और WhatsApp पर</li>
<li style="margin:6px 0">• आगरा, फिरोजाबाद, लखनऊ में district-level जनसंवाद कार्यक्रम</li>
<li style="margin:6px 0">• Smart Meter Demo Campaign — 'आपका Smart Meter कैसे काम करता है' video series</li>
</ul>
</div>
<div style="margin-top:24px;padding:12px;background:#f9fafb;border:1px solid #e5e7eb;font-size:12px;color:#6b7280">
DEMO report — Production system generates this automatically from live MySQL data every day at 8 AM IST.
</div>
</body></html>"""


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    port = int(os.environ.get("PORT", 8000))
    is_local = port == 8000
    print("\n" + "="*60)
    print("  Matrix AI Sahayak — DEMO MODE")
    print("="*60)
    print(f"\n  URL: http://localhost:{port}")
    print(f"  API Docs: http://localhost:{port}/api/docs")
    print(f"  Sample Report: http://localhost:{port}/api/v2/reports/RPT-DEMO/html")
    print("\n  Demo queries to try:")
    print("  • Smart meter protest ke baare mein batao")
    print("  • Agra mein kya hua smart meter ko lekar?")
    print("  • Sentiment analysis karo")
    print("  • AAP ka role kya hai is protest mein?")
    print("  • Lucknow mein kya situation hai?")
    print("\n  Press Ctrl+C to stop")
    print("="*60 + "\n")

    if is_local:
        def open_browser():
            time.sleep(1.5)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
