FROM iwaseyusuke/mininet:latest

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


WORKDIR /app

COPY run_no_sdn.py /app/run_no_sdn.py
COPY run_sdn_traditional.py /app/run_sdn_traditional.py
COPY run_sdn_qlearning.py /app/run_sdn_qlearning.py

COPY traffic-generator /app/traffic-generator

ENV PYTHONPATH="/app:${PYTHONPATH}"

CMD ["/bin/bash"]
