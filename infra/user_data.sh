#!/bin/bash
# Exécuté automatiquement au premier démarrage de la VM : installe Docker.
set -e
apt-get update
apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu
# Swap de 2 Go : évite les plantages mémoire pendant les builds Docker
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
