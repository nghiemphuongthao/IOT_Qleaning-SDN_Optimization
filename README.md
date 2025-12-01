# IoT-SDN-Qlearning Project (Level 3 - Distributed with ZeroMQ)

## Yêu cầu
- Docker, Docker Compose
- Máy có >=8GB RAM (nên có GPU nếu train nhanh)
- Chạy trên Linux preferred (Mininet privileged)

## Chạy nhanh
1. Build & run:
docker compose build --no-cache
docker compose up --build

2. Logs:
docker logs -f ryu-controller
docker logs -f qlearning-agent
docker logs -f mininet-topology
docker logs -f traffic-generator


## Lưu ý
- Mininet container cần `privileged: true`.
- Nếu container name conflict, `docker rm -f <name>` trước.
- Models, logs, results lưu ở folder `./shared`.