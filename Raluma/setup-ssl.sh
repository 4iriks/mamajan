#!/bin/bash
# Run this script on VPS after DNS has propagated to get SSL cert and enable HTTPS
# Usage: bash /opt/mamajan/Raluma/setup-ssl.sh

set -e
DOMAIN="raluma.tech"
EMAIL="admin@raluma.tech"  # change to your email
DIR="/opt/mamajan/Raluma"

echo "Getting SSL certificate for $DOMAIN..."

# Get cert via webroot (nginx stays running)
docker run --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v raluma_certbot_webroot:/var/www/certbot \
  certbot/certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" -d "www.$DOMAIN" \
  --email "$EMAIL" \
  --agree-tos --non-interactive

echo "Certificate obtained! Switching to SSL config..."

# Swap nginx config and rebuild frontend
cp "$DIR/nginx-ssl.conf" "$DIR/nginx.conf"
docker compose -f "$DIR/docker-compose.yml" up -d --build frontend

echo "Done! Site is now available at https://$DOMAIN"
