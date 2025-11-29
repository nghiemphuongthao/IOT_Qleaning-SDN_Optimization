#!/bin/bash
echo "=== SDN Performance Comparison: Baseline vs SDN vs SDN+Qlearning ==="

timestamp=$(date +%Y%m%d_%H%M%S)
mkdir -p results/comparison_${timestamp}

run_case() {
    local case_name=$1
    local ryu_container="ryu-controller-${case_name}"
    local mininet_container="mininet-${case_name}"
    local traffic_container="traffic-generator-${case_name}"
    
    echo "=== Starting Case: $case_name ==="
    
    # Start Ryu controller
    echo "Starting Ryu controller for $case_name..."
    docker-compose up -d $ryu_container
    sleep 10
    
    # Start Mininet topology
    echo "Starting Mininet for $case_name..."
    docker-compose up -d $mininet_container
    sleep 15
    
    # Start traffic generator
    echo "Starting traffic generation for $case_name..."
    docker-compose up -d $traffic_container
    
    # Run experiment for 5 minutes
    echo "Running experiment for 300 seconds..."
    sleep 300
    
    # Collect results
    echo "Collecting results for $case_name..."
    docker-compose logs $ryu_container > "results/comparison_${timestamp}/${case_name}_ryu.log"
    docker-compose logs $traffic_container > "results/comparison_${timestamp}/${case_name}_traffic.log"
    
    # Get performance metrics from Ryu API
    curl -s "http://localhost:808$(get_port_suffix $case_name)/stats/switches" > "results/comparison_${timestamp}/${case_name}_switches.json"
    curl -s "http://localhost:808$(get_port_suffix $case_name)/stats/flow/1" > "results/comparison_${timestamp}/${case_name}_flows.json"
    
    # Stop case
    echo "Stopping $case_name case..."
    docker-compose stop $traffic_container $mininet_container $ryu_container
    
    echo "=== Case $case_name Completed ==="
    echo ""
}

get_port_suffix() {
    case $1 in
        "baseline") echo "1" ;;
        "sdn") echo "2" ;;
        "sdn-qlearning") echo "3" ;;
    esac
}

# Run each case sequentially
run_case "baseline"
run_case "sdn" 

# For SDN+Qlearning, start Q-learning agent first
echo "=== Starting Q-learning Agent ==="
docker-compose up -d qlearning-agent
sleep 10

run_case "sdn-qlearning"

# Run analysis
echo "=== Starting Comparative Analysis ==="
docker-compose up -d analysis
sleep 30

docker-compose logs analysis > "results/comparison_${timestamp}/analysis.log"

# Stop all services
docker-compose down

echo "=== All Experiments Completed ==="
echo "Results saved to: results/comparison_${timestamp}/"