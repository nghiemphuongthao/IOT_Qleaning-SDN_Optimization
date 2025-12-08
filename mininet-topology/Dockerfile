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

# Copy file topo + entrypoint
COPY topology.py /topo/topology.py
COPY entrypoint.sh /topo/entrypoint.sh
COPY topologies /topo/topologies
COPY traffic-generator /traffic-generator

WORKDIR /topo

ENV PYTHONPATH="/topo:/topo/topologies:${PYTHONPATH}"

RUN chmod +x /topo/entrypoint.sh

ENTRYPOINT ["/topo/entrypoint.sh"]
