#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist-release
docker image save -o dist-release/images.tar nachat-app:0.1.0 nachat-web:0.1.0 postgres:17.7-alpine redis:7.4.7-alpine
cp compose.yaml compose.lan.yaml .env.example README.md ARCHITECTURE.md DESIGN_REVIEW.md VALIDATION.md dist-release/
cp Docker起動手順.txt Windows社内テスト手順.txt dist-release/
mkdir -p dist-release/docs
cp docs/*.md dist-release/docs/
mkdir -p dist-release/infra
cp infra/nginx.tls.conf infra/backup.sh infra/restore.sh infra/backup.ps1 infra/restore.ps1 infra/initialize-config.ps1 dist-release/infra/
docker compose images --format json > dist-release/images.json
echo 'Package: dist-release (no secrets or user data included)'
