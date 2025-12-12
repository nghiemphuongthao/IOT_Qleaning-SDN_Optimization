FROM iwaseyusuke/mininet:latest

# Cài thêm các gói cần thiết (nếu còn thiếu)
RUN apt-get update && \
    apt-get install -y \
        openvswitch-switch \
        iproute2 \
        iputils-ping \
        net-tools \
        python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y netcat-openbsd


# Copy file topo + entrypoint
COPY topology.py /app/topology.py
COPY entrypoint.sh /app/entrypoint.sh
COPY topologies /app/topologies
COPY traffic-generator /app/traffic-generator

WORKDIR /app

ENV PYTHONPATH="/app:/app/topologies:${PYTHONPATH}"

RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
