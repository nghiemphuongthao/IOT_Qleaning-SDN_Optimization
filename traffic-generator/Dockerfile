# traffic-generator/Dockerfile
FROM python:3.8-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    iperf3 iputils-ping iproute2 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt || true

COPY traffic.py /app/traffic.py
RUN chmod +x /app/traffic.py

CMD ["python3", "/app/traffic.py", "sdn"]
