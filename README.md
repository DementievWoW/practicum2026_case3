# SQL Security Multi-Agent

NL→SQL с аудитом безопасности. Цикл «генератор → судья → reflection-фикс»,
один LLM на оба агента (асимметричный few-shot). Артефакт системы — SQL +
audit log, без исполнения на проде.

## Быстрый старт (всё в docker)

```bash
bash scripts/setup.sh            # создаст .env + secrets/ + сгенерит ключи
docker compose up -d --build     # поднимет 6 сервисов
```

После `setup.sh` без правок будет работать **MockLLM** (для демо без сети).
Чтобы подключить реальную LLM (Qwen2.5-Coder через OpenRouter):

```bash
echo 'sk-or-v1-...' > secrets/llm_api_key   # ваш ключ → docker secret
docker compose up -d                        # recreate app с реальным LLM
```

Проверка:

```bash
curl -s -X POST localhost:18000/audit -H 'Content-Type: application/json' \
     -d '{"task":"Сколько кредитных договоров?"}' | python3 -m json.tool
```

Сервисы (нестандартные хост-порты, чтобы не конфликтовать с другими стеками):

| URL | Что |
|---|---|
| http://localhost:18000/healthz | FastAPI live-проба |
| http://localhost:18000/audit   | POST `{"task":"..."}` → SQL + audit_log |
| http://localhost:19100/metrics | Prometheus exposition (Counter/Histogram/Gauge) |
| http://localhost:19090         | Prometheus UI |
| http://localhost:13000         | Grafana (admin/admin), дашборд «SQL Security» |
| http://localhost:13001         | Langfuse v2 (логин из `.env`) |
| postgresql://distr_user:pass@localhost:15432/demo_db | demo_db (60 таблиц, ~500 строк/таблицу) |

## Без docker (локально)

```bash
pip install -r requirements.txt
set -a; source .env; set +a
PYTHONPATH=.:src python3.10 scripts/ex_eval.py    # → EX 26/26 (100%), ~1.4s/задачу
PYTHONPATH=.:src uvicorn case3.infra.service:app --port 8000
```

## Структура

```
src/case3/
  pipeline.py                 # цикл генератор→судья→reflector (run_pipeline)
  contracts.py                # ре-экспорт baseline + Finding/Lesson
  nodes/
    generator.py              # LLMGenerator (positive few-shot + reflection)
    auditor.py                # HybridAuditor (Phase 1 правила + Phase 2 LLM)
    reflector.py              # детерминированные уроки по vuln_class
  schema/
    linker.py                 # DAIL Code-Repr DDL, FK-хинты, лексический ранкер
  audit/
    sensitive.py              # PII-паттерны (телефон, ИНН, email, паспорт, счёт)
    schema_sensitive.py       # schema-grounded PII (по комментариям каталога)
    knowledge.py              # RAG: правила R001..R013
  llm/
    factory.py                # make_llm(): OpenAI-compat | Colab | Mock
    openai_compat.py          # клиент с LLM_API_KEY_FILE fallback (docker secrets)
  infra/
    service.py                # FastAPI: /healthz /metrics /audit
    runtime.py                # run_instrumented (метрики + трейсы вокруг pipeline)
    metrics.py                # stdlib-реестр Prometheus
    tracing.py                # StubTracer + Langfuse fallback

deploy/
  init-db/01_schema.sql       # 60 таблиц для postgres /docker-entrypoint-initdb.d
  seed/Dockerfile             # одноразовый сидер (faker + introspect)
  observability/
    prometheus.yml            # scrape targets: app:9100 (+ host fallback)
    grafana/                  # provisioning + dashboards
docker-compose.yml            # полный стек
Dockerfile                    # app образ (python:3.11-slim, ~150 МБ)
.dockerignore                 # без .git/secrets/notebooks в build-контекст
```

## Метрики кейса

- **EX** (Execution Accuracy на 26 задачах: агрегаты / ORDER BY+LIMIT / joins / широкие таблицы) — **26/26 (100%)**
- **Латентность** — ~1.4 сек / задачу (Qwen2.5-Coder-32B-Instruct через OpenRouter)
- **Классы уязвимостей** — 13 правил (R001..R013), 0–10 risk score, маппинг в `baseline.VULN_CLASSES`

## Безопасность

- `.env` и `secrets/` — в `.gitignore`.
- API-ключ читается из docker secret (`LLM_API_KEY_FILE=/run/secrets/llm_api_key`)
  с fallback на `LLM_API_KEY` env. См. `src/case3/llm/openai_compat.py`.
- Если секрета нет — система поднимется на `MockLLMClient` (`make_llm()` в `llm/factory.py`).
