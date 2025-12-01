FROM python:3.7

RUN apt-get update && apt-get install -y \
    build-essential curl net-tools iproute2 iputils-ping \
    && rm -rf /var/lib/apt/lists/*

RUN pip install "eventlet==0.30.2"


RUN pip install --no-cache-dir ryu pyzmq networkx

WORKDIR /app
COPY . /app
CMD ["ryu-manager", "--observe-links", "ryu_app.py"]