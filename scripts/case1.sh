#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"

run_case \
  docker-compose.no-sdn.yml \
  "CASE1 no_sdn" \
  docker exec mininet python3 run_no_sdn.py
