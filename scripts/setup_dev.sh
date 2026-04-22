#!/bin/bash
# PHQ Development Environment Setup
# Run once on a fresh machine after cloning the repo.
set -e

echo "=== PHQ Intelligence Bot — Dev Setup ==="

# 1. Start infrastructure containers
echo "[1/4] Starting Docker services..."
docker-compose -f infrastructure/docker/docker-compose.yml up -d \
  zookeeper kafka qdrant neo4j timescaledb elasticsearch redis
echo "Waiting 30s for services to initialize..."
sleep 30

# 2. Python backend
echo "[2/4] Installing Python dependencies..."
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
echo "  -> Edit backend/.env and add your API keys"

# 3. Download LLM model (optional — prompts user)
echo "[3/4] LLM model setup..."
echo "  To enable AI-generated answers, download Llama 3 8B:"
echo "  1. Visit: https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF"
echo "  2. Download: Meta-Llama-3-8B-Instruct.Q4_K_M.gguf (~4.9 GB)"
echo "  3. Place at: /models/llama3/Meta-Llama-3-8B-Instruct.Q4_K_M.gguf"
echo "  (System works in mock mode without the model)"

# 4. Frontend
echo "[4/4] Installing frontend dependencies..."
cd ../frontend
npm install

echo ""
echo "=== Setup complete ==="
echo ""
echo "To start the system:"
echo "  Backend:  cd backend && source .venv/bin/activate && uvicorn api.main:app --reload"
echo "  Worker:   cd backend && python -m enrichment.kafka_consumer"
echo "  Frontend: cd frontend && npm run dev"
echo ""
echo "Dashboard: http://localhost:5173"
echo "API docs:  http://localhost:8000/api/docs"
echo "Neo4j UI:  http://localhost:7474"
echo "Airflow:   http://localhost:8080 (admin/admin)"
