FROM iwaseyusuke/mininet:latest

# -----------------------
# System dependencies
# -----------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openvswitch-switch \
        iproute2 \
        iputils-ping \
        net-tools \
        netcat-openbsd \
        python3 \
        python3-pip && \
    rm -rf /var/lib/apt/lists/*

# -----------------------
# Project files
# -----------------------
WORKDIR /app

# Topology & scripts
COPY run_no_sdn.py /app/run_no_sdn.py
COPY run_sdn_traditional.py /app/run_sdn_traditional.py
COPY run_sdn_qlearning.py /app/run_sdn_qlearning.py



# Traffic generator
COPY traffic-generator /app/traffic-generator

# -----------------------
# Python path
# -----------------------
ENV PYTHONPATH="/app:${PYTHONPATH}"

# -----------------------
# Default command
# -----------------------
CMD ["/bin/bash"]
