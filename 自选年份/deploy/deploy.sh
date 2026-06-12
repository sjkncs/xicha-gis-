#!/bin/bash
# ================================================================
# deploy.sh — Deploy 15分钟生活圈 to globalreviewops.xyz (Linux)
# ================================================================
# Run on the server or via SSH:
#   chmod +x deploy.sh && ./deploy.sh
#
# Or run locally with scp/ssh:
#   bash deploy.sh
# ================================================================

set -e

# ── CONFIG ────────────────────────────────────────────────────
SERVER="${SERVER:-root@globalreviewops.xyz}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"
STATIC_DIR="/var/www/globalreviewops-15min"
API_PORT="${API_PORT:-8765}"
API_MODULE="routing_api"
LOCAL_OUTPUT="../city_twin_output"
# ───────────────────────────────────────────────────────────────

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
die()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo "======================================================"
echo "  15分钟生活圈 Deploy — globalreviewops.xyz"
echo "======================================================"

# Check local files
[[ -f "$LOCAL_OUTPUT/city_twin_viewer.html" ]] || die "Viewer not found. Run: python city_twin_builder.py"
[[ -f "$LOCAL_OUTPUT/base_data.json" ]]         || die "base_data.json not found"
log "Local files found"

# 1. Upload static files
echo ""
echo "[1/4] Uploading static files..."
ssh -i "$SSH_KEY" "$SERVER" "mkdir -p $STATIC_DIR"
scp -i "$SSH_KEY" \
    "$LOCAL_OUTPUT/city_twin_viewer.html" \
    "$LOCAL_OUTPUT/base_data.json" \
    "$LOCAL_OUTPUT/trajectory_data.json" \
    "$SERVER:$STATIC_DIR/"
log "Static files uploaded"

# 2. Install Nginx config
echo ""
echo "[2/4] Installing Nginx config..."
scp -i "$SSH_KEY" "nginx-globalreviewops.conf" "$SERVER:/tmp/"
ssh -i "$SSH_KEY" "$SERVER" <<'ENDSSH'
sudo cp /tmp/nginx-globalreviewops.conf /etc/nginx/sites-available/globalreviewops-15min
sudo ln -sf /etc/nginx/sites-available/globalreviewops-15min /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
ENDSSH
log "Nginx configured"

# 3. Restart FastAPI
echo ""
echo "[3/4] Restarting FastAPI on port $API_PORT..."
ssh -i "$SSH_KEY" "$SERVER" <<'ENDSSH'
cd "$STATIC_DIR"
pkill -f "uvicorn $API_MODULE" 2>/dev/null || true
sleep 1
nohup python -m uvicorn $API_MODULE:app --host 0.0.0.0 --port $API_PORT \
    > /var/log/15min-api.log 2>&1 &
sleep 3
curl -s http://localhost:$API_PORT/ | head -c 100
ENDSSH
log "API running"

# 4. Smoke test
echo ""
echo "[4/4] HTTPS smoke test..."
sleep 2
HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://$SERVER/api/stats")
if [[ "$HTTP_CODE" == "200" ]]; then
    log "HTTPS smoke test passed (HTTP $HTTP_CODE)"
else
    warn "HTTPS smoke test got HTTP $HTTP_CODE — check SSL certs and Nginx proxy_pass"
fi

echo ""
echo "======================================================"
echo -e "  Deploy complete!"
echo -e "  View at: ${GREEN}https://globalreviewops.xyz/city_twin_viewer.html${NC}"
echo -e "  API docs: ${GREEN}https://globalreviewops.xyz/docs${NC}"
echo "======================================================"
