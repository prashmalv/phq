# Government Intelligence Bot (PHQ)
## AI-Powered Decision Support System for Police HQ, Uttar Pradesh
### Hybrid RAG + Knowledge Graph | On-Premise Deployment

---

## Architecture Overview

```
LAYER 1: DATA SOURCES
  X/Twitter · Facebook · Instagram · YouTube · News Portals · Govt Records

LAYER 2: ETL + NLP ENRICHMENT
  Language Detection · Geo-tagging · Event Classification · Sentiment Scoring

LAYER 3: HYBRID STORAGE
  Neo4j (Graph) · Qdrant (Vector) · TimescaleDB (Time-Series) · Elasticsearch (Full-Text)

LAYER 4: AI QUERY ORCHESTRATOR
  LangGraph Agent + Llama 3 (private, on-premise)

LAYER 5: OFFICER INTERFACE
  React Chat UI (Hindi + English)
```

---

## Phase-wise Delivery

| Phase | Duration | Scope |
|-------|----------|-------|
| Phase 1 | Months 1–2 | Infrastructure + Ingestion + Vector DB + Basic RAG |
| Phase 2 | Months 2–3 | Graph DB + TimescaleDB + NLP + Multi-DB Orchestration |
| Phase 3 | Months 4–5 | YouTube/Audio + Real-time Alerts + CAG Caching + Full Rollout |

---

## Project Structure

```
PHQ/
├── backend/
│   ├── ingestion/       # Kafka consumers, social media + news scrapers
│   ├── enrichment/      # NLP pipeline (NER, geo, sentiment, classification)
│   ├── storage/         # DB clients: Qdrant, Neo4j, TimescaleDB, Elasticsearch
│   ├── orchestrator/    # LangGraph agent, query routing, answer generation
│   └── api/             # FastAPI REST endpoints for frontend
├── frontend/            # React chat interface (Hindi + English)
├── infrastructure/
│   ├── docker/          # docker-compose for all services
│   ├── airflow/dags/    # Scheduled ingestion DAGs
│   └── nginx/           # Reverse proxy config
├── scripts/             # Setup, seed, migration scripts
└── docs/                # Client questionnaire, API docs
```

---

## Quick Start (Development)

```bash
# 1. Start all infrastructure services
docker-compose -f infrastructure/docker/docker-compose.yml up -d

# 2. Install backend dependencies
cd backend && pip install -r requirements.txt

# 3. Run API server
cd backend/api && uvicorn main:app --reload --port 8000

# 4. Start frontend
cd frontend && npm install && npm run dev
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Data Ingestion | Apache Kafka + Airflow |
| NLP Pipeline | IndicNLP + mBERT / XLM-R |
| Graph Database | Neo4j Community Edition |
| Vector Database | Qdrant (self-hosted) |
| Time-Series DB | TimescaleDB (PostgreSQL extension) |
| Full-Text Search | Elasticsearch |
| AI Orchestrator | LangGraph + Llama 3 |
| API Server | FastAPI (Python) |
| Frontend | React + Vite |
| Security | Keycloak + Audit Log |
