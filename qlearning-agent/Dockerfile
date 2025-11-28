FROM python:3.9-slim

# Cài đặt các gói cần thiết
RUN apt-get update && apt-get install -y curl && \
    pip install requests numpy pandas matplotlib

# Tạo thư mục làm việc
WORKDIR /agent

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn Q-learning
COPY q_agent.py .
COPY network_state_collector.py . 

# Tạo thư mục để lưu mô hình và kết quả
RUN mkdir -p /shared/models /shared/results /shared/logs

# Mount thư mục shared từ host để lưu dữ liệu training
VOLUME ["/shared"]

# Lệnh khởi động chính
CMD ["python", "q_agent.py"]
