#!/usr/bin/env bash
set -euo pipefail

RUN_SECONDS="${RUN_SECONDS:-300}"
BULK_METER_KBPS="${BULK_METER_KBPS:-1200}"
BULK_MAX_BPS="${BULK_MAX_BPS:-1200000}"

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

run_case() {
  local compose_file="$1"
  local label="$2"
  shift 2

  echo ""
  echo "============================================================"
  echo "RUN: ${label}"
  echo "RUN_SECONDS=${RUN_SECONDS}"
  echo "============================================================"

  RUN_SECONDS="${RUN_SECONDS}" \
  BULK_METER_KBPS="${BULK_METER_KBPS}" \
  BULK_MAX_BPS="${BULK_MAX_BPS}" \
  docker compose -f "${compose_file}" up -d --build --force-recreate --remove-orphans "$@"

  wait_mininet_ready

  echo "[run] experiment running for ${RUN_SECONDS}s..."
  sleep "${RUN_SECONDS}"

  echo "[cleanup] stopping containers"
  docker compose -f "${compose_file}" down --remove-orphans
}

run_report() {
  echo ""
  echo "============================================================"
  echo "RUN: REPORT (analysis)"
  echo "============================================================"

  docker compose -f docker-compose.report.yml up --build --abort-on-container-exit
  docker compose -f docker-compose.report.yml down --remove-orphans
}

main() {
  run_case docker-compose.no-sdn.yml "CASE1 no_sdn" mininet
  run_case docker-compose.yml "CASE2 sdn_traditional" ryu-controller mininet
  run_case docker-compose.sdn-qlearning.yml "CASE3 sdn_qlearning" qlearning-agent ryu-controller mininet
  run_report

  echo ""
  echo "DONE. Check:"
  echo "- ./shared/raw/*.csv"
  echo "- ./shared/results/summary.csv"
  echo "- ./shared/results/*.png"
  echo "- ./shared/results/qlearning_*.png (if case3 ran + agent log existed)"
}

main "$@"
