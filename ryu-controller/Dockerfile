FROM python:3.7

RUN apt-get update && apt-get install -y \
    build-essential curl net-tools iproute2 iputils-ping \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "eventlet==0.30.2"


RUN pip install --no-cache-dir ryu pyzmq networkx

WORKDIR /app
COPY . /app

EXPOSE 6633 8080 5556 5557

CMD ["ryu-manager",\
     "--ofp-listen-host", "0.0.0.0",\
     "--ofp-tcp-listen-port", "6633",\
     "ryu.topology.switches",\
     "/app/ryu_app.py"]


