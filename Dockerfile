# Образ нашего приложения: FastAPI-сервис /audit + /metrics + /healthz.
# База: python:3.11-slim (≈45 МБ) — psycopg2-binary колёса уже под manylinux.
# Сборка: docker build -t sqlsec-app:latest .
# Используется в deploy/docker-compose.yml сервисом `app`.
FROM python:3.11-slim

# stdout без буфера → логи в `docker logs` идут сразу
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app/src:/app

# Системные пакеты: curl нужен для healthcheck в compose (psycopg2-binary
# не требует системных libpq благодаря wheel-сборке)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала только requirements.txt — слой кэшируется, пока зависимости не меняются
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код и данные (схема-каталог, baseline-контракт)
COPY src/ ./src/
COPY data/ ./data/
COPY baseline1.py .

# Непривилегированный пользователь — best practice для контейнера
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

# 8000 — FastAPI, 9100 — Prometheus /metrics (раздаёт infra/metrics.py)
EXPOSE 8000 9100

# Лёгкий self-check (на случай если кто-то запустит без compose)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "case3.infra.service:app", "--host", "0.0.0.0", "--port", "8000"]
