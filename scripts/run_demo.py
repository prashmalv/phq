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
import sys
import threading
import time
import uuid
import webbrowser
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


def _match_query(query: str) -> dict:
    q = query.lower()
    for keyword, response in MOCK_ANSWERS.items():
        if keyword in q:
            return response
    return {
        "answer": f"""**Query:** "{query}"

यह demo में {len(MOCK_ANSWERS)} sample topics cover हैं:
• Smart Meter protest की जानकारी
• Agra जिले की situation
• Lucknow में protest
• Sentiment analysis
• AAP की भूमिका

इन topics पर कोई भी question पूछें। Production में यह bot 14 लाख+ real social media records से answer देगा।""",
        "confidence": 0.5,
        "evidence_count": 0,
        "sources": ["Demo Mode"],
        "district_detected": None,
        "latency_ms": 200,
    }


@app.get("/", response_class=HTMLResponse)
@app.get("/ai-bot/", response_class=HTMLResponse)
async def serve_chat():
    index = _dedicated / "index.html"
    if index.exists():
        content = index.read_text()
        content = content.replace('href="app.css"', 'href="/static/app/app.css"')
        content = content.replace('src="app.js"',   'src="/static/app/app.js"')
        # Inject demo answers — JS uses these directly, no network call needed
        answers_json = json.dumps({k: {
            "answer": v["answer"], "confidence": v["confidence"],
            "evidence_count": v["evidence_count"], "sources": v["sources"],
            "latency_ms": v["latency_ms"],
        } for k, v in MOCK_ANSWERS.items()})
        content = content.replace('</head>',
            f'<script>window.DEMO_ANSWERS={answers_json};</script></head>')
        banner = (
            '<div style="background:#d97706;color:#fff;text-align:center;'
            'padding:7px 12px;font-size:12.5px;font-weight:500;">'
            '🎯 DEMO MODE — Mock data from Smart Meter Agitation (Apr–May 2026). '
            'Production will use live MySQL data.</div>'
        )
        content = content.replace("<body>", f"<body>{banner}")
        return HTMLResponse(content)
    return HTMLResponse("<h2>Matrix AI Sahayak — Demo Mode</h2>"
                        "<p>Run from repo root: <code>./demo.sh</code></p>")


@app.post("/api/v2/chat/query")
async def chat_query(
    request: dict,
    authorization: str = Header(default="Bearer demo"),
):
    query = request.get("query", "")
    session_id = request.get("session_id") or None

    # Create new session only if no valid existing session sent
    if not session_id or session_id not in _sessions:
        session_id = _make_session_id()

    response = _match_query(query)
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
    port = 8000
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

    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
