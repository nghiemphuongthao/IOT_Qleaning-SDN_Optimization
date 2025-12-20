# IoT SDN + Q-learning (Ryu)

Ports:
- Critical UDP 5001
- Telemetry UDP 5002
- Bulk TCP 5003

Run:
- case1: CASE=0 docker compose up
- case2: CASE=1 docker compose up
- case3: CASE=2 docker compose up

Analysis:
python3 analysis/collect_metrics.py
python3 analysis/compare_cases.py



cách mở xterm: xhost +si:localuser:root