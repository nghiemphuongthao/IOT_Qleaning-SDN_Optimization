qlearning:
	docker compose -f docker-compose.sdn-qlearning.yml up -d --build --remove-orphans
down-qlearning:
	docker compose -f docker-compose.sdn-qlearning.yml down 
log-ryu:
	docker logs -f ryu-controller
log-agent:
	docker logs -f qlearning-agent 

run-all:
	bash scripts/case1.sh && bash scripts/case2.sh && bash scripts/case3.sh

run:
	bash scripts/run2.sh

report:
	bash scripts/report.sh
.PHONY: qlearning down-qlearning log-ryu log-agent run-all run report