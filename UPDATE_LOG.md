# 📌 Update Log

## 🗓️ Ngày: 2025-11-25

### 🔧 Phiên bản: v1.0.3

- 🔄 **Dockerfile Ryu ([docker/ryu-python37](./docker/ryu-python37/Dockerfile))**: chuyển base image từ `python:3.8` xuống `python:3.7` để tương thích tốt hơn.
- 📂 **Q-learning Agent ([docker/qlearning-python39](./docker/qlearning-python39/requirements.txt))**: tạo file `requirements.txt` riêng trong thư mục `docker/qlearning-python39` để build image độc lập.
- 🛠️ **setup_environment.sh ([scripts/setup_environment.sh](./scripts/setup_environment.sh))**: cập nhật logic kiểm tra Docker Compose, hỗ trợ cả hai phiên bản:
  - `docker-compose` (legacy binary)
  - `docker compose` (plugin mới).
- 🧩 **run_experiment.py ([scripts/run_experiment.py](./scripts/run_experiment.py))**: refactor để chạy bằng `docker-compose` hoặc `docker compose` tùy phiên bản phát hiện.
- 🌐 **Docker Network**: thay đổi subnet từ `172.24.0.0/24` sang `172.25.0.0/24` để tránh xung đột địa chỉ.
- 📝 **.gitignore ([.gitignore](./.gitignore))**: thêm file `.gitignore` để loại bỏ các thư mục sinh ra trong quá trình chạy thí nghiệm:
  - `logs/`
  - `models/`
  - `results/`

---
