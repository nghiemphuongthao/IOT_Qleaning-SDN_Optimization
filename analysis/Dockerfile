FROM python:3.11-slim
WORKDIR /app

COPY analysis/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY analysis/collect_metrics.py analysis/compare_cases.py analysis/qlearning_analysis.py analysis/run_all.py /app/

CMD ["python", "run_all.py"]
