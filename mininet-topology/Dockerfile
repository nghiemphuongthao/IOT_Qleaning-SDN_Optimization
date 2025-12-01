FROM iwaseyusuke/mininet:latest

# Cài các gói cần thiết
RUN apt-get update && \
    apt-get install -y \
        openvswitch-switch \
        iproute2 \
        iputils-ping \
        net-tools \
        python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Copy topo
COPY topology.py /topo/topology.py
COPY entrypoint.sh /topo/entrypoint.sh
WORKDIR /topo

# Đặt quyền thực thi cho entrypoint
RUN chmod +x entrypoint.sh

# Khởi chạy entrypoint
ENTRYPOINT ["./entrypoint.sh"]
