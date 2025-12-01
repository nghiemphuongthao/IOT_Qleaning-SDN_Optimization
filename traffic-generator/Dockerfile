FROM python:3.9-slim
RUN apt-get update && apt-get install -y iperf3 curl && rm -rf /var/lib/apt/lists/*
COPY generator.py /gen/generator.py
WORKDIR /gen
CMD ["python", "generator.py"]
