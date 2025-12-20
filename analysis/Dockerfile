FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY collect_metrics.py compare_cases.py plot_rl_only.py  qlearning_log.csv /app/

CMD ["python", "plot_rl_only.py"]

