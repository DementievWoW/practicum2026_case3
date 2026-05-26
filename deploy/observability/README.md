# Наблюдаемость · Участник 4

Стек наблюдаемости: приложение отдаёт метрики, Prometheus их скрейпит,
Grafana рисует дашборд, Langfuse v2 пишет трейсы LLM-цепочек. Всё локально,
без внешних сервисов.

> История:
> - метрики — `src/case3/infra/metrics.py` (stdlib-реестр; drop-in под `prometheus_client`);
> - трейсинг — `src/case3/infra/tracing.py` (StubTracer → Langfuse v2 в compose);
> - БД-песочница — `src/case3/infra/db.py` (Stub → реальная Postgres из compose).

## Запуск (в составе общего стека)

Compose-файл лежит в корне репозитория — там же `.env` рядом, поэтому:

```bash
# из корня репозитория
docker compose up -d           # поднимет всё: db + seeder + app + prom + grafana + langfuse
docker compose ps              # статус сервисов
```

Открыть (порты нестандартные — чтобы не конфликтовать с другими стеками):
- **FastAPI**     — http://localhost:18000/healthz, POST /audit `{"task":"..."}`
- **/metrics**    — http://localhost:19100/metrics
- **Prometheus** — http://localhost:19090 (таргет `sqlsec-app` должен быть `UP`)
- **Grafana**    — http://localhost:13000 (admin/admin), дашборд «SQL Security»
- **Langfuse**   — http://localhost:13001 (логин из `.env`)

## Метрики приложения

| Метрика | Тип | Что показывает |
|---|---|---|
| `sqlsec_runs_total{approved}` | counter | прогоны пайплайна, в разрезе одобрено/нет |
| `sqlsec_iterations` | histogram | сколько итераций ушло на прогон |
| `sqlsec_latency_seconds` | histogram | латентность прогона |
| `sqlsec_last_risk` | gauge | итоговый risk последнего прогона (порог 4.0) |
| `sqlsec_findings_total{vuln_class}` | counter | найдено уязвимостей по классам |

Источник — `src/case3/infra/metrics.py`, пишет их `infra/runtime.run_instrumented()`,
которая обёрнута вокруг `pipeline.run_pipeline()` (контракт baseline не трогаем).

## Только наблюдаемость (без приложения в compose)

Старый сценарий: приложение запускается на хосте, а только Grafana/Prometheus в docker.
Для этого в `prometheus.yml` оставлен fallback-таргет `host.docker.internal:9100`,
а отдельный compose-файл этой папки можно поднимать руками:

```bash
python -m case3.infra.runtime          # /metrics на :9100 хоста
cd deploy/observability
docker compose -f docker-compose.host.yml up   # см. файл в этой папке (если нужен)
```

Но штатный путь — корневой `docker-compose.yml`, там оба варианта таргета прописаны.
