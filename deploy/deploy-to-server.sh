#!/usr/bin/env bash
# deploy-to-server.sh
# Uso: bash deploy-to-server.sh

set -e

SERVER="viaje"
REMOTE_PATH="/var/www/daily_readings"
COUNTER_SERVICE="daily-news-counter"

echo "=== daily_news: Deploy a $SERVER ==="

# 1. Rsync archivos estáticos
echo "[1/4] Subiendo estático..."
rsync -avz --delete --exclude=.git output/ "$SERVER:$REMOTE_PATH/"

# 2. Nginx config
echo "[2/4] Configurando nginx..."
scp deploy/nginx.conf "$SERVER:/tmp/intelligence-hub-nginx"
ssh "$SERVER" "sudo mv /tmp/intelligence-hub-nginx /etc/nginx/sites-available/intelligence-hub && sudo ln -sf /etc/nginx/sites-available/intelligence-hub /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx"

# 3. Contador service (systemd)
echo "[3/4] Instalando contador..."
ssh "$SERVER" "mkdir -p $REMOTE_PATH"
scp src/counter_server.py "$SERVER:$REMOTE_PATH/counter_server.py"
ssh "$SERVER" "sudo tee /etc/systemd/system/$COUNTER_SERVICE.service > /dev/null <<'EOF'
[Unit]
Description=Daily News Visit Counter
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=$REMOTE_PATH
ExecStart=/usr/bin/python3 $REMOTE_PATH/counter_server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload && sudo systemctl enable $COUNTER_SERVICE && sudo systemctl restart $COUNTER_SERVICE"

# 4. Verificar
echo "[4/4] Verificando..."
sleep 2
curl -s "https://news.viajeinteligencia.com/api/count" || echo "⚠️  Verifica manual: curl https://news.viajeinteligencia.com/api/count"

echo "=== Deploy completado ==="
