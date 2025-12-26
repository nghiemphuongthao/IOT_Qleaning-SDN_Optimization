#!/usr/bin/env bash
set -euo pipefail

RUN_SECONDS="${RUN_SECONDS:-90}"
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

  # Nếu còn argument → đó là command
  local has_cmd=0
  local cmd=()
  if [ "$#" -gt 0 ]; then
    has_cmd=1
    cmd=( "$@" )
  fi

  echo ""
  echo "============================================================"
  echo "RUN: ${label}"
  echo "RUN_SECONDS=${RUN_SECONDS}"
  echo "============================================================"

  RUN_SECONDS="${RUN_SECONDS}" \
  BULK_METER_KBPS="${BULK_METER_KBPS}" \
  BULK_MAX_BPS="${BULK_MAX_BPS}" \
  docker compose -f "${compose_file}" up -d \
    --build \
    --force-recreate \
    --remove-orphans

  wait_mininet_ready

  if [ "$has_cmd" -eq 1 ]; then
    echo "[run] executing command:"
    echo "  ${cmd[*]}"
    "${cmd[@]}"
  else
    echo "[run] no command specified, sleeping ${RUN_SECONDS}s..."
    sleep "${RUN_SECONDS}"
  fi

  echo "[cleanup] stopping containers"
  docker compose -f "${compose_file}" down --remove-orphans
}
