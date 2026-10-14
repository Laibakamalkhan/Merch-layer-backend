FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY api_main.py ./
COPY src ./src
COPY config ./config
COPY mappings ./mappings
COPY manifests ./manifests
COPY migrations ./migrations

RUN pip install --no-cache-dir .

CMD ["sh", "-c", "uvicorn api_main:app --host 0.0.0.0 --port ${PORT:-8000}"]
