#!/bin/bash
# Matrix AI Sahayak — Server Setup Script
# Run once on the H200 server after extracting the zip
# Usage: cd /opt/matrix-ai-sahayak && bash infrastructure/setup_server.sh

set -e

DEPLOY_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$DEPLOY_DIR/.venv"
SERVICE_NAME="matrix-ai-sahayak"

echo ""
echo "=============================================="
echo "  Matrix AI Sahayak — Server Setup"
echo "=============================================="
echo "  Deploy dir: $DEPLOY_DIR"
echo ""

# ── 1. Python virtualenv ──────────────────────────────────────────────────────
echo "[1/5] Creating Python virtualenv..."
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$DEPLOY_DIR/backend/requirements.txt" -q
echo "      Done."

# ── 2. .env file ──────────────────────────────────────────────────────────────
echo "[2/5] Checking .env..."
if [ ! -f "$DEPLOY_DIR/.env" ]; then
    cp "$DEPLOY_DIR/backend/.env.example" "$DEPLOY_DIR/.env"
    echo ""
    echo "  ⚠️  .env file created from template."
    echo "  EDIT IT NOW: nano $DEPLOY_DIR/.env"
    echo "  Fill in: SMTP_PASSWORD, REPORT_EMAIL_RECIPIENTS, LLM_MODEL_PATH"
    echo ""
else
    echo "      .env already exists — skipping."
fi

# ── 3. Qdrant (Docker) ───────────────────────────────────────────────────────
echo "[3/5] Starting Qdrant vector DB (Docker)..."
if command -v docker &>/dev/null; then
    docker run -d --name qdrant --restart unless-stopped \
        -p 6333:6333 -p 6334:6334 \
        -v qdrant_storage:/qdrant/storage \
        qdrant/qdrant:latest 2>/dev/null || echo "      Qdrant already running."
else
    echo "      ⚠️  Docker not found — install Docker first, then re-run."
fi

# ── 4. Systemd service ────────────────────────────────────────────────────────
echo "[4/5] Installing systemd service..."
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=Matrix AI Sahayak
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$DEPLOY_DIR
EnvironmentFile=$DEPLOY_DIR/.env
ExecStart=$VENV/bin/uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
echo "      Service installed."

# ── 5. Start service ──────────────────────────────────────────────────────────
echo "[5/5] Starting service..."
sudo systemctl restart "$SERVICE_NAME"
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "      ✅ Service is running."
else
    echo "      ❌ Service failed to start. Check logs:"
    echo "         journalctl -u $SERVICE_NAME -n 30"
fi

echo ""
echo "=============================================="
echo "  Setup complete!"
echo ""
echo "  Check status : systemctl status $SERVICE_NAME"
echo "  View logs    : journalctl -u $SERVICE_NAME -f"
echo "  Test API     : curl http://localhost:8000/api/health"
echo ""
echo "  Next steps:"
echo "  1. Configure nginx (see infrastructure/nginx/)"
echo "  2. Download LLM model to path in .env"
echo "  3. First embedding sync will run automatically"
echo "=============================================="
