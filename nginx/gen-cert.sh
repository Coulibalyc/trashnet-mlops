#!/bin/sh
# Crée un certificat HTTPS auto-signé au premier démarrage de Nginx (s'il n'existe pas déjà).
mkdir -p /etc/nginx/certs
if [ ! -f /etc/nginx/certs/cert.pem ]; then
  command -v openssl >/dev/null || apk add --no-cache openssl >/dev/null
  openssl req -x509 -nodes -newkey rsa:2048 -days 365 -subj "/CN=trashnet" \
    -keyout /etc/nginx/certs/key.pem -out /etc/nginx/certs/cert.pem
fi
