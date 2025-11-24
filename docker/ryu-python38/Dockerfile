FROM python:3.8-slim

RUN apt-get update && apt-get install -y \
    git \
    gcc \
    net-tools \
    && rm -rf /var/lib/apt/lists/*

RUN pip install ryu==4.34

WORKDIR /app

EXPOSE 6633 8080

CMD ["ryu-manager", "--version"]