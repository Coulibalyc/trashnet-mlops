#!/usr/bin/env bash
# Déploie le projet sur la VM en une commande :   ./scripts/deploy.sh <IP_DE_LA_VM>
# 1) copie le code sur la VM   2) relance les conteneurs   3) vérifie que l'API répond
set -euo pipefail
HOST="${1:?Usage: ./scripts/deploy.sh <IP>}"
KEY="${SSH_KEY:-$HOME/.ssh/trashnet}"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new ubuntu@$HOST"

echo "==> Attente de Docker sur la VM"
$SSH 'until command -v docker >/dev/null; do sleep 5; done'

echo "==> Copie du code"
rsync -az --delete -e "ssh -i $KEY -o StrictHostKeyChecking=accept-new" \
  --exclude .git --exclude data --exclude 'infra/.terraform*' --exclude 'infra/*.tfstate*' \
  --exclude .env --exclude results ./ "ubuntu@$HOST:~/trashnet/"

echo "==> Fichier .env"
if [ -n "${ADMIN_TOKEN:-}" ]; then      # cas GitHub Actions : secrets -> .env
  $SSH "printf 'ADMIN_TOKEN=%s\nPOSTGRES_PASSWORD=%s\nAPI_REPLICAS=%s\n' '$ADMIN_TOKEN' '$POSTGRES_PASSWORD' '${API_REPLICAS:-3}' > ~/trashnet/.env"
elif [ -f .env ]; then                   # cas local : on copie notre .env
  scp -i "$KEY" .env "ubuntu@$HOST:~/trashnet/.env"
fi

echo "==> Lancement des conteneurs"
$SSH 'cd ~/trashnet && docker compose up -d --build --remove-orphans && docker compose ps'

echo "==> Vérification"
for i in $(seq 1 30); do
  if curl -fs "http://$HOST/api/health"; then echo; echo "Déploiement OK -> http://$HOST"; exit 0; fi
  sleep 5
done
echo "L'API ne répond pas" && exit 1
