FROM python:3.7

RUN apt-get update && apt-get install -y build-essential python3-dev libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pyzmq numpy scipy tensorflow==2.11.0 scikit-learn

WORKDIR /agent
COPY . /agent
CMD ["python", "q_agent.py"]