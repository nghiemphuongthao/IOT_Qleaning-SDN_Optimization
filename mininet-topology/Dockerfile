FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# --------------------------------------------------
# 1. Cài dependency cần cho Mininet + OVS
# --------------------------------------------------
RUN apt-get update && apt-get install -y \
    sudo \
    git \
    curl \
    iproute2 \
    iputils-ping \
    net-tools \
    python3 \
    python3-pip \
    python3-setuptools \
    python3-dev \
    build-essential \
    tcpdump \
    openvswitch-switch \
    ethtool \
    iperf3 \
    telnet \
    socat \
    psmisc \
    xterm \
    help2man \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------
# 2. Clone Mininet và cài Mininet (không chạy install.sh)
# --------------------------------------------------
RUN git clone https://github.com/mininet/mininet.git /opt/mininet

# Cài đặt Mininet bằng cách copy trực tiếp
RUN cd /opt/mininet && \
    python3 setup.py install

# --------------------------------------------------
# 3. Copy topology.py vào container
# --------------------------------------------------
WORKDIR /app
COPY topology.py /app/topology.py

# --------------------------------------------------
# 4. Khởi động OVS khi chạy container
# --------------------------------------------------
CMD service openvswitch-switch start && python3 topology.py
