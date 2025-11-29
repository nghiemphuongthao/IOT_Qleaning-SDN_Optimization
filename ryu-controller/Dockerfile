FROM osrg/ryu:4.31

# Cài curl để test health check (tuỳ chọn)
RUN apt-get update && apt-get install -y curl

WORKDIR /app

# Copy controller app
COPY app.py /app/app.py

# Expose OpenFlow và REST API
EXPOSE 6633 6653 8080

# Start Ryu với REST API và OpenFlow 1.3
CMD ["ryu-manager", "--ofp-tcp-listen-port", "6633", "--wsapi-port", "8080", "app.py"]
