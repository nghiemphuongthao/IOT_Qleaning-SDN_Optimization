#!/bin/bash
set -e

echo "Starting Mininet container (CASE=$CASE, MODE=$MODE)"

# Đợi Ryu
until nc -z ryu-controller 6653; do
  echo "Waiting for Ryu controller (6653)..."
  sleep 1
done

echo "Ryu controller ready"

# 🔴 QUAN TRỌNG: CHỈ CHẠY MININET Ở ĐÂY
python3 /app/topology.py
