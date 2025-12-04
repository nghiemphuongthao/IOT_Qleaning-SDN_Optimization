#!/bin/bash
set -e

echo ">>> Starting Open vSwitch..."

# Ensure dirs exist
mkdir -p /var/run/openvswitch
mkdir -p /var/log/openvswitch
mkdir -p /etc/openvswitch

# Create DB if missing
if [ ! -f /etc/openvswitch/conf.db ]; then
    echo ">>> Creating OVS DB"
    ovsdb-tool create /etc/openvswitch/conf.db /usr/share/openvswitch/vswitch.ovsschema
fi

# Start ovsdb-server
ovsdb-server --remote=punix:/var/run/openvswitch/db.sock \
             --remote=db:Open_vSwitch,Open_vSwitch,manager_options \
             --log-file=/var/log/openvswitch/ovsdb-server.log \
             --pidfile --detach

# Init DB
ovs-vsctl --no-wait init

# Start ovs-vswitchd
ovs-vswitchd --log-file=/var/log/openvswitch/ovs-vswitchd.log \
             --pidfile --detach

echo ">>> OVS is running."

echo "MODE = $MODE"

# ========================
# CASE 1: No controller
# ========================
if [ "$MODE" == "case1" ]; then
    echo "[Mininet] Running CASE 1 – Static (NO CONTROLLER)"
    python3 topology.py --mode case1
    exit 0
fi

# ========================
# CASE 2 & 3: require Ryu
# ========================
echo "[Mininet] CASE $MODE – requires Ryu controller"
echo "Waiting for Ryu controller at ryu-controller:6633 ..."
sleep 3

python3 topology.py --mode "$MODE"
