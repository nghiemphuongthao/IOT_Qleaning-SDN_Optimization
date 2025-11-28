FROM python:3.7-slim

RUN apt-get update && apt-get install -y git iproute2 && \
    pip install --no-cache-dir eventlet==0.30.2 ryu flask requests && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app.py /app/app.py


EXPOSE 8080 6633

CMD ["ryu-manager", "--observe-links", "app.py"]
