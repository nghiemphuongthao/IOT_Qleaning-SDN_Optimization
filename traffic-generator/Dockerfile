FROM python:3.8

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY traffic.py .

CMD ["python3", "traffic.py"]