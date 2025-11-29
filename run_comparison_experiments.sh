#!/bin/bash

echo "=== SDN Performance Comparison: Baseline vs SDN vs SDN+Qlearning ==="

# Clean up
docker-compose down --remove-orphans
docker network prune -f

timestamp=$(date +%Y%m%d_%H%M%S)
mkdir -p results/comparison_${timestamp}

run_case() {
    local case_name=$1
    local mininet_service="mininet-${case_name}"
    local traffic_service="traffic-generator"  # Using the same traffic generator for all
    
    echo "=== Starting Case: $case_name ==="
    
    # Start Mininet topology
    echo "Starting Mininet for $case_name..."
    docker-compose up -d $mininet_service
    sleep 15
    
    # Start traffic generator
    echo "Starting traffic generation for $case_name..."
    docker-compose up -d $traffic_service
    
    # For SDN cases, start Ryu controller
    if [ "$case_name" != "baseline" ]; then
        local ryu_service="ryu-controller-${case_name}"
        echo "Starting Ryu controller for $case_name..."
        docker-compose up -d $ryu_service
        sleep 10
    fi
    
    # For Q-learning case, start agent
    if [ "$case_name" == "sdn-qlearning" ]; then
        echo "Starting Q-learning agent..."
        docker-compose up -d qlearning-agent
        sleep 10
    fi
    
    # Run experiment for 2 minutes
    echo "Running experiment for 120 seconds..."
    sleep 120
    
    # Collect results
    echo "Collecting results for $case_name..."
    docker-compose logs $mininet_service > "results/comparison_${timestamp}/${case_name}_mininet.log"
    docker-compose logs $traffic_service > "results/comparison_${timestamp}/${case_name}_traffic.log"
    
    # Collect Ryu stats for SDN cases
    if [ "$case_name" != "baseline" ]; then
        local port=""
        if [ "$case_name" == "sdn" ]; then
            port="8082"
        elif [ "$case_name" == "sdn-qlearning" ]; then
            port="8083"
        fi
        
        curl -s "http://localhost:${port}/stats/switches" > "results/comparison_${timestamp}/${case_name}_switches.json"
        curl -s "http://localhost:${port}/stats/flow/1" > "results/comparison_${timestamp}/${case_name}_flows.json"
    fi
    
    # Stop case services
    echo "Stopping $case_name case..."
    docker-compose stop $traffic_service $mininet_service
    if [ "$case_name" != "baseline" ]; then
        docker-compose stop $ryu_service
    fi
    
    echo "=== Case $case_name Completed ==="
    echo ""
}

# Run each case
run_case "baseline"
run_case "sdn" 
run_case "sdn-qlearning"

# Run analysis
echo "=== Starting Analysis ==="
docker-compose up -d analysis
sleep 30
docker-compose logs analysis > "results/comparison_${timestamp}/analysis.log"

# Stop all services
docker-compose down

echo "=== All Experiments Completed ==="
echo "Results saved to: results/comparison_${timestamp}/"