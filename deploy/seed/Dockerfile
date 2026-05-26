# Однократный сидер БД: интроспектит схему, заливает ~N синтетических строк.
# Отдельный образ — чтобы prod-образ (Dockerfile в корне) не тянул `faker`.
# Запускается один раз compose-сервисом `seeder` через `restart: "no"`.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir psycopg2-binary>=2.9 faker>=24.0

WORKDIR /work
COPY scripts/seed_db_generic.py /work/seed_db_generic.py

# N строк на таблицу можно переопределить через env / `command:` в compose
ENV SEED_N=500

CMD ["sh", "-c", "python /work/seed_db_generic.py $SEED_N"]
