# Production image. The build runs the ETL and trains the model, so the
# container is self-contained and starts serving immediately (Cloud Run friendly).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    APP_ROOT=/app

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[agent,postgres]"

COPY sql ./sql
COPY data/raw ./data/raw

# Build-time ETL + training against the bundled SQLite warehouse.
RUN python -m churn.etl && python -m churn.train

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/health')"

CMD ["sh", "-c", "uvicorn churn.api:app --host 0.0.0.0 --port ${PORT}"]
