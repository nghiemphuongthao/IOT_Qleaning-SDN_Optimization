#!/usr/bin/env bash
set -euo pipefail

echo ""
echo "============================================================"
echo "RUN: REPORT (analysis)"
echo "============================================================"

docker compose -f docker-compose.report.yml up --build --abort-on-container-exit
docker compose -f docker-compose.report.yml down --remove-orphans
