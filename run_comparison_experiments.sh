#!/bin/bash
set -e

echo "=== SDN Performance Comparison: Baseline vs SDN vs SDN+Qlearning ==="

docker compose down --remove-orphans
docker network prune -f

timestamp=$(date +%Y%m%d_%H%M%S)
result_dir="results/comparison_${timestamp}"
mkdir -p "$result_dir"

# -----------------------------
# RUN A SINGLE CASE
# -----------------------------
run_case() {
    local case_name=$1

    echo ""
    echo "=============================="
    echo "    RUNNING CASE: $case_name"
    echo "=============================="

    # Select controller + mode
    if [ "$case_name" == "baseline" ]; then
        mode="baseline"
        ryu_service=""
    elif [ "$case_name" == "sdn" ]; then
        mode="sdn"
        ryu_service="ryu-controller-sdn"
    elif [ "$case_name" == "sdn-qlearning" ]; then
        mode="sdn_qlearning"
        ryu_service="ryu-controller-sdn-qlearning"
    fi

    echo "→ Mode: $mode"

    # Start controller if needed
    if [ ! -z "$ryu_service" ]; then
        echo "→ Starting RYU controller: $ryu_service"
        docker compose up -d "$ryu_service"
        sleep 10
    fi

    # Start Mininet with correct env
    echo "→ Starting Mininet..."
    docker compose up -d mininet
    docker compose exec -d mininet bash -c "export MODE=$mode; python3 run_topology.py"
    sleep 10

    # Start traffic generator
    echo "→ Starting Traffic Generator..."
    docker compose up -d traffic-generator
    docker compose exec -d traffic-generator bash -c "export MODE=$mode"

    # Start Q-Learning Agent if needed
    if [ "$case_name" == "sdn-qlearning" ]; then
        echo "→ Starting Q-learning Agent..."
        docker compose up -d qlearning-agent
        sleep 5
    fi

    # Run experiment
    echo "→ Running experiment for 120s..."
    sleep 120

    # ---------------- Collect Logs ----------------
    echo "→ Collecting logs..."
    docker compose logs mininet > "$result_dir/${case_name}_mininet.log"
    docker compose logs traffic-generator > "$result_dir/${case_name}_traffic.log"

    if [ ! -z "$ryu_service" ]; then
        port="8082"
        [ "$case_name" == "sdn-qlearning" ] && port="8083"

        curl -s "http://localhost:${port}/stats/switches" > "$result_dir/${case_name}_switches.json"
        curl -s "http://localhost:${port}/stats/flow/1" > "$result_dir/${case_name}_flows.json"
    fi

    # Stop all running containers for this case
    echo "→ Stopping all services for case: $case_name"
    docker compose stop traffic-generator mininet
    [ ! -z "$ryu_service" ] && docker compose stop "$ryu_service"
    [ "$case_name" == "sdn-qlearning" ] && docker compose stop qlearning-agent

    echo "=== CASE DONE: $case_name ==="
}

# -----------------------------
# RUN ALL CASES
# -----------------------------
run_case "baseline"
run_case "sdn"
run_case "sdn-qlearning"

# -----------------------------
# ANALYSIS
# -----------------------------
echo ""
echo "=== STARTING ANALYSIS ==="
docker compose up -d analysis
sleep 20
docker compose logs analysis > "$result_dir/analysis.log"

docker compose down

echo ""
echo "=== ALL EXPERIMENTS COMPLETED ==="
echo "Results saved to: $result_dir"
