"""
Intelligence Report Generator.

Produces detailed social media intelligence reports from MySQL aggregate data + LLM synthesis.
Format matches the official Social Media Report format used by PHQ UP.
"""
import asyncio
from datetime import datetime
from typing import Optional

from loguru import logger

from backend.config import settings
from backend.sync.mysql_connector import MySQLConnector
from backend.orchestrator.llm_client import LLMClient
from backend.reports.store import create_report, save_report

_REPORT_SYSTEM = """You are a senior intelligence analyst at Police HQ, Uttar Pradesh.
Write intelligence report sections in Hindi. Be concise, factual, and action-oriented.
Use only the data provided — do not hallucinate incidents or statistics."""


class ReportGenerator:
    def __init__(self):
        self.mysql = MySQLConnector()
        self.llm = LLMClient()

    async def generate(
        self,
        title: str,
        from_date: str,
        to_date: str,
        trigger: str = "manual",
    ) -> str:
        """Generate a full report. Returns report_id."""
        report_id = create_report(title, from_date, to_date, trigger)
        logger.info(f"Generating report {report_id}: {title}")
        try:
            stats = self._gather_stats(from_date, to_date)
            narrative = await self._generate_narrative(title, from_date, to_date, stats)
            html = _render_html(title, from_date, to_date, stats, narrative, report_id)
            save_report(report_id, html, {
                "title": title,
                "from_date": from_date,
                "to_date": to_date,
                "total_posts": stats["total"],
                "top_district": stats["district_counts"][0]["district"] if stats["district_counts"] else None,
            })
            logger.info(f"Report {report_id} complete")
            return report_id
        except Exception as e:
            logger.error(f"Report {report_id} failed: {e}")
            save_report(report_id, f"<p>Generation error: {e}</p>", {}, status="failed")
            return report_id

    def _gather_stats(self, from_date: str, to_date: str) -> dict:
        daily = self.mysql.get_post_counts_by_date(from_date, to_date)
        districts = self.mysql.get_post_counts_by_district(from_date, to_date)
        sentiment = self.mysql.get_sentiment_breakdown(from_date, to_date)
        platform = self.mysql.get_platform_breakdown(from_date, to_date)
        topics = self.mysql.get_top_topics_by_period(from_date, to_date)
        matrix = self.mysql.get_district_date_matrix(from_date, to_date)
        total = sum(d["count"] for d in daily)
        peak_day = max(daily, key=lambda x: x["count"], default={})
        return {
            "total": total,
            "daily_counts": daily,
            "district_counts": districts,
            "sentiment": sentiment,
            "platform": platform,
            "topics": topics,
            "matrix": matrix,
            "peak_day": peak_day,
        }

    async def _generate_narrative(self, title, from_date, to_date, stats) -> dict:
        total = stats["total"]
        top_district = stats["district_counts"][0]["district"] if stats["district_counts"] else "Unknown"
        peak = stats["peak_day"]
        neg = sum(s["count"] for s in stats["sentiment"]
                  if "neg" in (s.get("sentiment_label") or "").lower())
        neg_pct = round(neg / max(total, 1) * 100, 1)

        daily_str = " | ".join(f"{d['date']}: {d['count']}" for d in stats["daily_counts"])
        dist_str = " | ".join(f"{d['district']}: {d['count']}" for d in stats["district_counts"][:5])
        topics_str = "\n".join(
            f"- {t['topic_title']} ({t.get('total_no_of_post', 0)} posts)"
            for t in stats["topics"][:5]
        ) or "- कोई विषय उपलब्ध नहीं"

        prompt = f"""निम्नलिखित social media intelligence data के आधार पर PHQ UP की intelligence report के ये sections लिखें:

रिपोर्ट: {title}
अवधि: {from_date} से {to_date}
कुल पोस्ट: {total}
नकारात्मक भावना: {neg_pct}%
सर्वाधिक सक्रिय जिला: {top_district}
सर्वाधिक सक्रिय दिन: {peak.get('date', 'N/A')} ({peak.get('count', 0)} पोस्ट)

दैनिक गतिविधि: {daily_str}
जिला-वार (शीर्ष 5): {dist_str}

प्रमुख विषय:
{topics_str}

प्रत्येक section का label लिखकर शुरू करें। केवल Hindi में। Factual रहें।

SUMMARY: (3-4 वाक्यों में घटना का सारांश)
NARRATIVES: (सोशल मीडिया पर फैल रहे 5 प्रमुख आख्यान — bullet points में)
SENTIMENT_ARC: (पूरी अवधि में भावना का प्रवाह — 2-3 वाक्य)
LAW_ORDER: (कानून-व्यवस्था की 3-4 प्रमुख चिंताएं — bullet points)
RECOMMENDATIONS: (सरकार के लिए 5 तत्काल सिफारिशें — bullet points)"""

        try:
            response = await self.llm.complete(prompt, system=_REPORT_SYSTEM, max_tokens=1200)
            return _parse_llm_sections(response)
        except Exception as e:
            logger.error(f"LLM narrative failed: {e}")
            return _fallback_narrative(total, neg_pct, top_district)


# ─── HTML Renderer ────────────────────────────────────────────────────────────

def _render_html(title, from_date, to_date, stats, narrative, report_id) -> str:
    now = datetime.utcnow().strftime("%d %b %Y, %H:%M UTC")
    total = stats["total"]
    peak = stats["peak_day"]
    neg = sum(s["count"] for s in stats["sentiment"]
              if "neg" in (s.get("sentiment_label") or "").lower())
    neg_pct = round(neg / max(total, 1) * 100, 1)
    pos = sum(s["count"] for s in stats["sentiment"]
              if "pos" in (s.get("sentiment_label") or "").lower())
    pos_pct = round(pos / max(total, 1) * 100, 1)
    neu_pct = round(100 - neg_pct - pos_pct, 1)

    # Sensitivity level based on sentiment
    if neg_pct >= 70:
        sensitivity = '<span style="color:#dc2626;font-weight:bold">🔴 High — व्यापक जनासंतोष और विधि-व्यवस्था संबंधी चिंताएं</span>'
    elif neg_pct >= 40:
        sensitivity = '<span style="color:#d97706;font-weight:bold">🟠 Medium — निगरानी आवश्यक</span>'
    else:
        sensitivity = '<span style="color:#16a34a;font-weight:bold">🟢 Low — सामान्य गतिविधि</span>'

    daily_rows = "".join(
        f"<tr><td>{d['date']}</td><td style='text-align:center'>{d['count']}</td>"
        f"<td>{'<span class=spike>Peak</span>' if d['count'] == peak.get('count') and d['count'] > 50 else ''}</td></tr>"
        for d in stats["daily_counts"]
    )
    district_rows = "".join(
        f"<tr><td>{i}</td><td>{d['district']}</td><td style='text-align:center'>{d['count']}</td></tr>"
        for i, d in enumerate(stats["district_counts"][:10], 1)
    )
    platform_rows = "".join(
        f"<tr><td>{p['platform']}</td><td style='text-align:center'>{p['count']}</td>"
        f"<td>{round(p['count']/max(total,1)*100,1)}%</td></tr>"
        for p in stats["platform"]
    )
    sentiment_rows = "".join(
        f"<tr><td>{s['sentiment_label']}</td><td style='text-align:center'>{s['count']}</td>"
        f"<td>{round(s['count']/max(total,1)*100,1)}%</td></tr>"
        for s in stats["sentiment"]
    )
    topic_rows = "".join(
        f"<tr><td>{i}</td><td>{t['topic_title']}</td><td>{t.get('broad_category','')}</td>"
        f"<td>{t.get('primary_districts','')}</td><td style='text-align:center'>{t.get('total_no_of_post',0)}</td></tr>"
        for i, t in enumerate(stats["topics"][:10], 1)
    )

    # Section 12: district × date matrix
    dates = sorted({str(r["date"]) for r in stats["matrix"]})
    districts_m = []
    seen = set()
    for r in stats["matrix"]:
        if r["district"] not in seen:
            districts_m.append(r["district"])
            seen.add(r["district"])

    matrix_header = "<th>District</th>" + "".join(f"<th>{d[5:]}</th>" for d in dates) + "<th>Total</th>"
    matrix_rows_html = ""
    for dist in districts_m[:20]:
        row_data = {r["date"]: r["count"] for r in stats["matrix"] if r["district"] == dist}
        row_total = sum(row_data.values())
        cells = "".join(f"<td style='text-align:center'>{row_data.get(d, 0) or ''}</td>" for d in dates)
        matrix_rows_html += f"<tr><td>{dist}</td>{cells}<td style='text-align:center;font-weight:bold'>{row_total}</td></tr>"

    def bullets(items):
        if isinstance(items, list):
            return "".join(f"<li>{i}</li>" for i in items if i)
        return f"<li>{items}</li>" if items else "<li>जानकारी उपलब्ध नहीं</li>"

    return f"""<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8"/>
<title>Social Media Intelligence Report — {title}</title>
<style>
  body{{font-family:Arial,sans-serif;max-width:1100px;margin:0 auto;padding:20px;color:#1a1a1a;font-size:14px}}
  .rpt-header{{background:#1a3a6b;color:#fff;padding:28px;text-align:center;margin-bottom:20px}}
  .rpt-header h1{{margin:0;font-size:22px;letter-spacing:1px}}
  .rpt-header p{{margin:6px 0 0;font-size:13px;opacity:.85}}
  .sec-head{{background:#1e4d8c;color:#fff;padding:9px 14px;font-weight:bold;font-size:14px;margin-top:22px}}
  .sub-head{{color:#1e4d8c;border-bottom:2px solid #1e4d8c;padding-bottom:4px;margin-top:14px;font-weight:bold}}
  table{{width:100%;border-collapse:collapse;margin:10px 0}}
  th{{background:#1e4d8c;color:#fff;padding:7px 10px;text-align:left;font-size:13px}}
  td{{padding:6px 10px;border-bottom:1px solid #e5e7eb;font-size:13px}}
  tr:nth-child(even){{background:#f9fafb}}
  .spike{{background:#dc2626;color:#fff;padding:2px 7px;border-radius:4px;font-size:11px}}
  .box-blue{{background:#eff6ff;border-left:4px solid #1e4d8c;padding:10px 14px;margin:8px 0}}
  .box-green{{background:#f0fdf4;border-left:4px solid #22c55e;padding:10px 14px;margin:8px 0}}
  .box-red{{background:#fef2f2;border-left:4px solid #dc2626;padding:10px 14px;margin:8px 0}}
  ul.bl{{list-style:none;padding:0;margin:6px 0}}
  ul.bl li::before{{content:"• ";color:#1e4d8c;font-weight:bold}}
  ul.bl li{{margin:4px 0}}
  .meta{{font-size:12px;color:#6b7280;text-align:right;margin-bottom:6px}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0}}
  .kpi{{background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:12px;text-align:center}}
  .kpi-val{{font-size:26px;font-weight:bold;color:#1e4d8c}}
  .kpi-label{{font-size:11px;color:#6b7280;margin-top:2px}}
  @media print{{.no-print{{display:none}}}}
</style>
</head>
<body>
<div class="rpt-header">
  <h1>Social Media Intelligence Report</h1>
  <p>Issue: {title}</p>
  <p>Reporting Period: {from_date} – {to_date} | Geography: Uttar Pradesh</p>
  <p style="font-size:11px;margin-top:8px">Report ID: {report_id} | Generated: {now} | PHQ Intelligence Bot</p>
</div>
<div class="meta">CONFIDENTIAL — For Senior Officers Only</div>

<div class="kpi-grid">
  <div class="kpi"><div class="kpi-val">{total:,}</div><div class="kpi-label">कुल पोस्ट/उल्लेख</div></div>
  <div class="kpi"><div class="kpi-val" style="color:#dc2626">{neg_pct}%</div><div class="kpi-label">नकारात्मक भावना</div></div>
  <div class="kpi"><div class="kpi-val">{peak.get('count',0)}</div><div class="kpi-label">Peak Day पोस्ट ({peak.get('date','N/A')})</div></div>
  <div class="kpi"><div class="kpi-val">{len(stats['district_counts'])}</div><div class="kpi-label">प्रभावित जिले</div></div>
</div>

<div class="sec-head">SECTION 1 — Brief Summary of the Incident</div>
<div class="sub-head">a) Incident Description</div>
<div class="box-blue"><p>{narrative.get('summary','')}</p></div>
<div class="sub-head">b) Narratives Being Circulated on Social Media</div>
<ul class="bl">{bullets(narrative.get('narratives',[]))}</ul>
<div class="sub-head">c) Sentiment Arc</div>
<div class="box-blue"><p>{narrative.get('sentiment_arc','')}</p></div>
<div class="sub-head">d) Sensitivity Level</div>
<div class="box-red">{sensitivity}</div>

<div class="sec-head">SECTION 2 — Activity and Pattern Analysis</div>
<div class="sub-head">Daily Post Volume</div>
<table>
  <tr><th>तारीख</th><th>पोस्ट/उल्लेख</th><th>Note</th></tr>
  {daily_rows}
  <tr style="background:#1e4d8c;color:#fff"><td><b>GRAND TOTAL</b></td><td style="text-align:center"><b>{total}</b></td><td></td></tr>
</table>
<div class="sub-head">Platform-wise Distribution</div>
<table>
  <tr><th>Platform</th><th>Posts</th><th>%</th></tr>
  {platform_rows}
</table>

<div class="sec-head">SECTION 3 — Public Sentiment Analysis</div>
<table>
  <tr><th>Sentiment</th><th>Posts</th><th>%</th></tr>
  {sentiment_rows}
</table>
<div class="sub-head">Law &amp; Order Concerns</div>
<ul class="bl">{bullets(narrative.get('law_order',[]))}</ul>

<div class="sec-head">SECTION 4 — Topic and Group Analysis</div>
<div class="sub-head">Top 10 Trending Topics</div>
<table>
  <tr><th>क्रम</th><th>Topic / मुद्दा</th><th>Category</th><th>Districts</th><th>Posts</th></tr>
  {topic_rows if topic_rows else '<tr><td colspan="5">No topics found for this period</td></tr>'}
</table>

<div class="sec-head">SECTION 5 — Geographic Analysis</div>
<div class="sub-head">District-wise Mention Distribution — Top 10</div>
<table>
  <tr><th>क्रम</th><th>जिला</th><th>Mentions</th></tr>
  {district_rows}
</table>

<div class="sec-head">SECTION 12 — District-wise Daily Activity Matrix</div>
<div style="overflow-x:auto">
<table>
  <tr>{matrix_header}</tr>
  {matrix_rows_html}
</table>
</div>

<div class="sec-head">SECTION 13 — Recommendations</div>
<div class="sub-head">Immediate Action Required (0–24 Hours)</div>
<div class="box-green"><ul class="bl">{bullets(narrative.get('recommendations',[]))}</ul></div>

<div style="margin-top:30px;padding:15px;background:#f9fafb;border:1px solid #e5e7eb;font-size:12px;color:#6b7280">
  <b>Note:</b> This report is auto-generated by PHQ Intelligence Bot from social media data in up_police_matrix database.
  Data is updated every 60 seconds. For queries, use the bot at <a href="https://aibot.matrixupp.com">aibot.matrixupp.com</a>.
</div>
</body>
</html>"""


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_llm_sections(text: str) -> dict:
    sections = {
        "summary": "", "narratives": [], "sentiment_arc": "",
        "law_order": [], "recommendations": [],
    }
    labels = {
        "SUMMARY:": "summary", "NARRATIVES:": "narratives",
        "SENTIMENT_ARC:": "sentiment_arc", "LAW_ORDER:": "law_order",
        "RECOMMENDATIONS:": "recommendations",
    }
    current = None
    buffer = []

    def flush():
        if not current:
            return
        text_block = "\n".join(buffer).strip()
        if current in ("narratives", "law_order", "recommendations"):
            items = [l.lstrip("•-* 0123456789.").strip() for l in text_block.split("\n") if l.strip()]
            sections[current] = [i for i in items if i]
        else:
            sections[current] = text_block

    for line in text.split("\n"):
        matched = False
        for label, key in labels.items():
            if line.startswith(label):
                flush()
                current = key
                buffer = [line[len(label):].strip()]
                matched = True
                break
        if not matched and current:
            buffer.append(line)
    flush()
    return sections


def _fallback_narrative(total, neg_pct, top_district) -> dict:
    return {
        "summary": f"इस अवधि में कुल {total} पोस्ट/उल्लेख दर्ज किए गए। सर्वाधिक सक्रिय जिला {top_district} रहा।",
        "narratives": ["विस्तृत आख्यान विश्लेषण के लिए LLM model configure करें।"],
        "sentiment_arc": f"कुल {neg_pct}% नकारात्मक भावना दर्ज की गई।",
        "law_order": ["विस्तृत कानून-व्यवस्था विश्लेषण उपलब्ध नहीं।"],
        "recommendations": ["LLM model configure करें automated recommendations के लिए।"],
    }
