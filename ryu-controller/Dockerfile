FROM python:3.7

WORKDIR /app

# Cài đặt các dependencies hệ thống
RUN apt-get update && apt-get install -y \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

RUN pip install eventlet==0.30.2    

# Cài đặt Ryu
RUN pip install ryu
RUN pip install networkx

COPY app.py .

# Expose ports cho OpenFlow và REST API
EXPOSE 6633 8080

CMD ["ryu-manager", "app.py", "--verbose", "--ofp-tcp-listen-port", "6633"]