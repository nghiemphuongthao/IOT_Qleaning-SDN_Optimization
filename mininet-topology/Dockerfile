FROM iwaseyusuke/mininet:latest

WORKDIR /app

COPY topology_baseline.py .
COPY topology_sdn.py .
COPY run_topology.py .

CMD ["python3", "run_topology.py"]