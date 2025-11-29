# Q-learning SDN Routing Project

This project implements a Q-learning based routing algorithm in Software-Defined Networks (SDN) using Mininet, Ryu controller, and a custom Q-learning agent.

## Project Structure
.
├── configs
│ ├── experiment.yaml
│ └── network_params.yaml
├── docker-compose.yml
├── mininet-topology
│ ├── Dockerfile
│ └── topology.py
├── qlearning-agent
│ ├── Dockerfile
│ ├── network_state_collector.py
│ ├── q_agent.py
│ └── requirements.txt
├── ryu-controller
│ ├── app.py
│ └── Dockerfile
└── traffic-generator
├── Dockerfile
└── traffic.py

text

## Components

- **Mininet Topology**: Creates the network topology with switches and hosts
- **Ryu Controller**: SDN controller that manages network flow rules
- **Q-learning Agent**: Implements reinforcement learning for optimal routing
- **Traffic Generator**: Generates network traffic for testing
- **Network State Collector**: Collects network statistics for the Q-learning agent

## Quick Start

1. Build and start the containers:
```bash
docker-compose up --build
The system will:

Create Mininet topology

Start Ryu controller

Launch Q-learning agent

Generate traffic patterns

▶ CASE 1 — Baseline (no SDN)
docker exec -it mininet bash -c "mn -c; python3 topology_baseline.py"
docker exec -d traffic-gen python3 traffic.py --mode baseline

▶ CASE 2 — SDN (Ryu)
docker exec -it mininet bash -c "mn -c; python3 topology_sdn.py"
docker exec -d traffic-gen python3 traffic.py --mode sdn

▶ CASE 3 — SDN + Q-learning
docker exec -d qagent python3 q_agent.py
docker exec -it mininet bash -c "mn -c; python3 topology_sdn.py"
docker exec -d traffic-gen python3 traffic.py --mode sdn_qlearning
