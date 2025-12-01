#!/bin/bash
set -e

# Lấy mode và IP controller từ environment
MODE=${TOPO_CASE:-standalone}
CONTROLLER_IP=${CONTROLLER_IP:-ryu-controller}

echo "*** Running topology.py (mode=$MODE, controller=$CONTROLLER_IP) ***"

# Start Open vSwitch daemons (cần cho standalone mode)
service openvswitch-switch start || true

# Chạy topology
python3 /topo/topology.py
