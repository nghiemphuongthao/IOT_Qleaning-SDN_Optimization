#!/usr/bin/env bash
set -euo pipefail

RUN_SECONDS=300

wait_mininet_ready() {
  echo "[wait] waiting for mininet container to be running..."
  for i in {1..30}; do
    if docker ps --format '{{.Names}}' | grep -qx 'mininet'; then
      echo "[wait] mininet is running"
      return 0
    fi
    sleep 1
  done
  echo "[error] mininet did not start in time"
  return 1
}

wait_ryu_ready() {
  echo "[wait] waiting for ryu-controller to be ready..."
  for i in {1..30}; do
    if docker exec ryu-controller ss -lnt 2>/dev/null | grep -q ':6633\|:6653'; then
      echo "[wait] ryu-controller is ready"
      return 0
    fi
    sleep 1
  done
  echo "[error] ryu-controller did not start in time"
  return 1
}

echo ""
echo "============================================================"
echo "RUN: CASE2 sdn_traditional (ryu-controller + mininet)"
echo "RUN_SECONDS=${RUN_SECONDS}"
echo "============================================================"

docker compose -f docker-compose.yml up -d \
  --build \
  --force-recreate \
  --remove-orphans

wait_ryu_ready
wait_mininet_ready
docker exec mininet python3 run_sdn_traditional.py

echo "[run] running SDN traditional for ${RUN_SECONDS}s..."
sleep "${RUN_SECONDS}"

echo "[cleanup] stopping containers"
docker compose -f docker-compose.yml down --remove-orphans
