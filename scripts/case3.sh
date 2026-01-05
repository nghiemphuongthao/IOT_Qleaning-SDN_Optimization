#!/usr/bin/env bash
set -euo pipefail

# ===== Config =====
RUN_SECONDS="${RUN_SECONDS:-300}"
BULK_METER_KBPS="${BULK_METER_KBPS:-1200}"
BULK_MAX_BPS="${BULK_MAX_BPS:-1200000}"
COMPOSE_FILE="docker-compose.sdn-qlearning.yml"

# ===== Wait functions =====
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

wait_agent_ready() {
  echo "[wait] waiting for qlearning-agent to be ready..."
  for i in {1..30}; do
    if docker ps --format '{{.Names}}' | grep -qx 'qlearning-agent'; then
      echo "[wait] qlearning-agent is running"
      return 0
    fi
    sleep 1
  done
  echo "[error] qlearning-agent did not start in time"
  return 1
}

# ===== Run =====
echo ""
echo "============================================================"
echo "RUN: CASE3 sdn_qlearning"
echo "RUN_SECONDS=${RUN_SECONDS}"
echo "============================================================"

RUN_SECONDS="${RUN_SECONDS}" \
BULK_METER_KBPS="${BULK_METER_KBPS}" \
BULK_MAX_BPS="${BULK_MAX_BPS}" \
docker compose -f "${COMPOSE_FILE}" up -d \
  --build \
  --force-recreate \
  --remove-orphans

wait_ryu_ready
wait_agent_ready
wait_mininet_ready
docker exec -e RUN_SECONDS="${RUN_SECONDS}" -e BULK_MAX_BPS="${BULK_MAX_BPS}" mininet python3 run_sdn_qlearning.py
echo "[run] running SDN Q-learning for ${RUN_SECONDS}s..."
sleep "${RUN_SECONDS}"

echo "[cleanup] stopping containers"
docker compose -f "${COMPOSE_FILE}" down --remove-orphans
