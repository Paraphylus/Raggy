FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HOST=0.0.0.0 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src
COPY demo/ ./demo
COPY data/ ./data

EXPOSE 8080

CMD ["sh", "-c", "uvicorn src.server:app --host ${HOST} --port ${PORT}"]

