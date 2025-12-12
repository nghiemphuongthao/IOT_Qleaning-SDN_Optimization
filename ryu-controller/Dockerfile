FROM python:3.7

RUN apt-get update && apt-get install -y \
    net-tools iproute2 iputils-ping curl gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir ryu==4.34 pyzmq networkx eventlet==0.30.2 numpy

COPY ryu_app.py iot_classifier.py /app/

# expose OF port and ZMQ ports
EXPOSE 6633 5556 5557

CMD ["ryu-manager", "ryu_app.py"]
