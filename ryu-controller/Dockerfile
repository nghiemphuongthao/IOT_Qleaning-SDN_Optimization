FROM python:3.7

RUN apt-get update && apt-get install -y \
    net-tools iproute2 iputils-ping curl gcc \
    && rm -rf /var/lib/apt/lists/* \
    netcat-openbsd

WORKDIR /app
COPY . /app


RUN pip install --no-cache-dir ryu==4.34 pyzmq networkx eventlet==0.30.2 numpy

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ryu_traditional.py /app/ryu_traditional.py
COPY q_agent.py model.py /app/

EXPOSE 6653 8080

