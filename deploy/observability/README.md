# Наблюдаемость (заглушка) · Участник 4

Стек наблюдаемости MVP на заглушках: приложение отдаёт метрики, Prometheus их
скрейпит, Grafana рисует дашборд. Всё работает локально, без внешних сервисов.

> Это **заглушки боевых интерфейсов**:
> - метрики — на stdlib (`src/case3/infra/metrics.py`), реальная версия `prometheus_client`;
> - трейсинг — `StubTracer` (`src/case3/infra/tracing.py`), реальная версия `langfuse` SDK;
> - БД-песочница — `StubDatabase` (`src/case3/infra/db.py`), реальная версия `psycopg`.
>
> Grafana и Prometheus — это уже настоящие образы; «заглушечность» в том, что
> данные им поставляет мок-приложение.

## Запуск

```bash
# 1. поднять приложение с /metrics и прогнать несколько задач
python -m case3.infra.runtime          # /metrics на :9100

# 2. в другом терминале — стек наблюдаемости
cd deploy/observability
docker compose up
```

Открыть:
- **Grafana** — http://localhost:3000 (`admin` / `admin`), дашборд **«SQL Security»** (папка General);
- **Prometheus** — http://localhost:9090 (таргет `sqlsec-app` должен быть `UP`);
- **/metrics** — http://localhost:9100/metrics (сырой текст).

## Метрики приложения

| Метрика | Тип | Что показывает |
|---|---|---|
| `sqlsec_runs_total{approved}` | counter | прогоны пайплайна, в разрезе одобрено/нет |
| `sqlsec_iterations` | histogram | сколько итераций ушло на прогон |
| `sqlsec_latency_seconds` | histogram | латентность прогона |
| `sqlsec_last_risk` | gauge | итоговый risk последнего прогона (порог 4.0) |
| `sqlsec_findings_total{vuln_class}` | counter | найдено уязвимостей по классам |

Источник метрик — `src/case3/infra/metrics.py`, пишет их `infra/runtime.run_instrumented()`.

## Что меняется при переходе на прод
- `StubTracer()` → `Langfuse(public_key=..., secret_key=..., host=...)`;
- stdlib-реестр метрик → `prometheus_client` (имена метрик те же);
- `StubDatabase()` → `psycopg`-коннект к Postgres-песочнице;
- `host.docker.internal:9100` в `prometheus.yml` → реальный адрес/сервис приложения.

Дашборд, провиженинг и PromQL остаются без изменений.
