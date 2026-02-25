#!/bin/bash
# Deploy raluma.tech on Ubuntu 24.04
# Run as root: bash deploy.sh
set -e

DIR="/opt/mamajan"

echo "=== [1] Clone / update repo ==="
if [ -d "$DIR/.git" ]; then
  cd "$DIR" && git pull origin main
else
  git clone https://github.com/4iriks/mamajan.git "$DIR"
fi

echo "=== [2] Build and start ==="
cd "$DIR/Raluma"
docker compose up -d --build

echo "=== [3] Check ==="
sleep 10
docker compose ps
curl -s http://localhost/health && echo " <- backend OK via Caddy"

echo "=== DONE ==="
