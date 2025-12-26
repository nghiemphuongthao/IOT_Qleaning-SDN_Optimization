# IoT SDN + Q-learning (Ryu) + QoS (Queue/Meter)

## Ports

- Critical UDP `5001`
- Telemetry UDP `5002`
- Bulk TCP `5003`

## Output folders

- `./shared/raw/`
  - `{case}_hX.csv`: sensor metrics (`rtt_ms`, `lost`, `sent`, `bps`)
  - `{case}_server.csv`: server-side bulk throughput (`bulk_mbps`)
- `./shared/results/`
  - `summary.csv`: aggregated metrics per case
  - `*.png`: comparison plots

## Run a case

### Case 1: No SDN (Linux routers)

```bash
RUN_SECONDS=90 docker compose -f docker-compose.no-sdn.yml up -d --build --force-recreate
```

### Case 2: SDN Traditional (static routing)

```bash
RUN_SECONDS=90 docker compose up -d --build --force-recreate
```

### Case 3: SDN + Q-learning Agent + QoS (queue + meter)

Key knobs:

- `RUN_SECONDS`: experiment duration (default `90`)
- `BULK_METER_KBPS`: meter police rate for bulk TCP (default `1200`)
- `BULK_MAX_BPS`: OVS queue max-rate for bulk (default `1200000`)

```bash
RUN_SECONDS=90 \
BULK_METER_KBPS=1200 \
BULK_MAX_BPS=1200000 \
docker compose -f docker-compose.sdn-qlearning.yml up -d --build --force-recreate
```

All three cases auto-generate traffic and write CSVs to `./shared/raw/`.

## Run analysis (comparison plots)

After you have data in `./shared/raw/` for the cases you want to compare:

```bash
docker compose -f docker-compose.report.yml up --build
```

Check:

- `./shared/results/summary.csv`
- `./shared/results/*.png`

## Run everything automatically

#### Run all cases sequentially (case1 -> case2 -> case3) and then run the analysis pipeline:

```bash
make run-all
```

Or:

```bash
bash scripts/run_all.sh
```

#### Run analysics
```
make report
```

#### Supported environment variables:

- `RUN_SECONDS` (default `90`)
- `BULK_METER_KBPS` (default `1200`)
- `BULK_MAX_BPS` (default `1200000`)

## Observability

### Curl: Q-learning Agent (localhost:5000)

```bash
curl -s http://localhost:5000/health
curl -s http://localhost:5000/debug/summary
curl -s "http://localhost:5000/debug/qtable?key=256:10.0.100" | head
```

Q-learning agent log:

- `./shared/raw/qlearning_agent_log.csv`

### Curl: Ryu Controller (localhost:8080)

```bash
curl -s http://localhost:8080/qos/routing | head
curl -s http://localhost:8080/qos/snapshot | head
curl -s http://localhost:8080/qos/agent | head
```

Ryu built-in OpenFlow REST (works for case2 and case3):

```bash
curl -s http://localhost:8080/stats/switches
curl -s http://localhost:8080/stats/desc/256 | head
curl -s http://localhost:8080/stats/flow/256 | head
curl -s http://localhost:8080/stats/port/256 | head
```

Notes:

- Case1 (no_sdn): no Ryu controller, so use Wireshark + CSV outputs.
- Case2 (sdn_traditional): use `/stats/*` endpoints above.
- Case3 (sdn_qlearning): use `/stats/*` plus `/qos/*` plus agent `localhost:5000`.

### Wireshark (PCAP capture)

Works for all three cases (no_sdn / sdn_traditional / sdn_qlearning): capture inside the `mininet` container and open the `.pcap` from `./shared/pcap/` on your host.

```bash
docker exec -it mininet bash -lc "mkdir -p /shared/pcap && tcpdump -i any '(udp port 5001 or udp port 5002 or tcp port 5003)' -w /shared/pcap/iot_<case>.pcap"
```

If you want a smaller capture, replace `-i any` with an interface like `cloud-eth0`.