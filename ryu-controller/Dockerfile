FROM python:3.7

RUN apt-get update && apt-get install -y \
    net-tools iproute2 iputils-ping curl gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir ryu==4.34 pyzmq networkx eventlet==0.30.2

# expose OF port and ZMQ ports
EXPOSE 6633 5556 5557

# IMPORTANT: options BEFORE apps. We pass only our app; if you want topology discovery app too,
# list it AFTER options (see below).
# CMD ["ryu-manager", "--observe-links", "/app/ryu_app.py", "ryu.topology.switches", "ryu.controller.ofp_handler"]
    # # CMD ["ryu-manager", "--ofp-tcp-listen-port", "6633", "ryu.topology.switches", "/app/ryu_app.py"]
    # CMD ["ryu-manager", "--observe-links", "/app/ryu_app.py", "ryu.topology.switches"]
CMD ["ryu-manager", "--ofp-listen-host", "0.0.0.0", "--ofp-tcp-listen-port", "6653", "/app/ryu_app.py", "ryu.topology.switches"]

