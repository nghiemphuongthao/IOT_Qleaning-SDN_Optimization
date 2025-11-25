FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

# Enable universe repo (needed for some packages)
RUN apt-get update && apt-get install -y software-properties-common \
    && add-apt-repository universe \
    && apt-get update

# Core system dependencies
RUN apt-get install -y \
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
    lsb-release \
    curl \
    wget \
    pkg-config \
    # Mininet dependencies (manual install instead of install.sh)
    openssh-client \
    psmisc \
    socat \
    xterm \
    telnet \
    help2man \
    python3-tk \
    python3-pexpect \
    pyflakes \
    python3-pycodestyle \
    pylint3 \
    openvswitch-switch \
    openvswitch-common \
    && rm -rf /var/lib/apt/lists/*

# Clone Mininet source (optional, for reference/examples)
RUN git clone https://github.com/mininet/mininet.git /tmp/mininet \
    && cd /tmp/mininet && git checkout -b 2.3.0 2.3.0

# Install Mininet Python package
RUN pip3 install mininet

WORKDIR /app

CMD ["mn", "--version"]
