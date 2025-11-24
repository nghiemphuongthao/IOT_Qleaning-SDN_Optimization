FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    git \
    sudo \
    apt-utils \
    net-tools \
    iputils-ping \
    iproute2 \
    tcpdump \
    iperf \
    ethtool \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/mininet/mininet.git /tmp/mininet
RUN cd /tmp/mininet && git checkout -b 2.3.0 2.3.0
RUN /tmp/mininet/util/install.sh -n

RUN apt-get update && apt-get install -y \
    openvswitch-switch \
    openvswitch-common

RUN pip3 install mininet

WORKDIR /app

CMD ["mn", "--version"]