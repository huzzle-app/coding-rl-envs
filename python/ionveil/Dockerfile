FROM python:3.12-slim

WORKDIR /app

# System dependencies for psycopg2, confluent-kafka
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8080 8081 8082 8083 8084 8085 8086 8087 8088 8089

CMD ["python", "-m", "services.gateway.app"]
