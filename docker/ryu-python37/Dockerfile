FROM python:3.7-slim

RUN apt-get update && apt-get install -y \
    git \
    gcc \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Ryu và eventlet phiên bản tương thích
RUN pip install --upgrade pip \
    && pip install "eventlet==0.30.2" \
    && pip install ryu==4.34

WORKDIR /app

EXPOSE 6633 8080

CMD ["ryu-manager", "--version"]
