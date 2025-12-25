qlearning:
	docker compose -f docker-compose.sdn-qlearning.yml up -d --build --remove-orphans
down-qlearning:
	docker compose -f docker-compose.sdn-qlearning.yml down 
log-ryu:
	docker logs -f ryu-controller
log-agent:
	docker logs -f qlearning-agent 

run-all:
	bash scripts/run_all.sh

.PHONY: qlearning down-qlearning log-ryu log-agent run-all