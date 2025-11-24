#!/bin/bash

echo "================================================"
echo " IoT SDN Q-learning - COMPLETE ENVIRONMENT SETUP"
echo "================================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check Docker
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    print_error "Docker Compose is not installed. Please install Docker Compose."
    exit 1
fi

print_status "Building Docker images..."
docker-compose build

print_status "Creating project directories..."
mkdir -p results/{baseline,ryu_sdn,qlearning_optimized,comparison}
mkdir -p logs
mkdir -p models
mkdir -p data/{raw,processed}

print_status "Setting up permissions..."
chmod +x scripts/*.py
chmod +x scripts/*.sh

print_status "Testing Docker setup..."
docker-compose up -d
sleep 10

# Test services
services=("ryu-controller" "mininet-topology" "qlearning-agent")
for service in "${services[@]}"; do
    if docker ps --format "table {{.Names}}" | grep -q "$service"; then
        print_status "✅ $service is running"
    else
        print_error "❌ $service is NOT running"
    fi
done

docker-compose down

print_status "================================================"
print_status "SETUP COMPLETED SUCCESSFULLY!"
print_status "To run the experiment:"
print_status "  python scripts/run_experiment.py"
print_status "================================================"