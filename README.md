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