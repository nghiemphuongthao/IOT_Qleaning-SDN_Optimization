FROM python:3.8

WORKDIR /app

RUN apt-get update && apt-get install -y python3-tk

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

VOLUME /shared

CMD ["python", "analyze_results.py"]
