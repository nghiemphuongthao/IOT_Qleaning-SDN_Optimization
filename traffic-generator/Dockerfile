FROM python:3.9-slim

# Cài đặt các gói cần thiết
RUN apt-get update && apt-get install -y iputils-ping curl && \
    pip install numpy pandas requests

# Sao chép mã sinh lưu lượng
WORKDIR /traffic
COPY traffic.py .

# Thư mục shared để lưu log nếu cần
RUN mkdir -p /shared/results /shared/logs
VOLUME ["/shared"]

# Lệnh chạy chính
CMD ["python", "traffic.py"]
