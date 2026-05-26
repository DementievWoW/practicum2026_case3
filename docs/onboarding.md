# Onboarding — развернуть локально за 5 минут

Для коллеги, который впервые клонировал репо. Если что-то не сходится —
смотри раздел **«Что обычно ломается»** в конце.

## 0. Что нужно поставить заранее

| Софт | Зачем | Версия | Проверка |
|---|---|---|---|
| Docker | контейнеры | 24+ | `docker --version` |
| docker-compose | `docker compose ...` (plugin v2) | 2.20+ | `docker compose version` |
| Python | для evaluator-скриптов на хосте | 3.10+ | `python3 --version` |
| make | команды `make up/check/...` | любой | `make --version` |
| git | клонировать репо | любой | `git --version` |
| openssl | генерация Langfuse-секретов | любой | `openssl version` |
| curl | smoke-test endpoints | любой | `curl --version` |

Всё остальное (Postgres, FastAPI, Prometheus, Grafana, Langfuse, Qwen-API,
HF Inference, pglast, faker) — в docker-контейнерах, ставить не нужно.

### Platform-specific

#### 🍎 macOS

```bash
# Docker Desktop: https://www.docker.com/products/docker-desktop/
brew install make python@3.11      # make и git обычно уже есть
```

Особенности:
- `make` доступен из коробки (Xcode CLT). Если ругается — `xcode-select --install`.
- `python` без `3` может быть Anaconda — наши скрипты ищут `python3`/`python` оба.
- `sed` — BSD (отличается от Linux GNU). В наших скриптах используется
  кросс-совместимый синтаксис `sed -i.bak '...'` + `rm .bak` — работает.

#### 🐧 Linux

Всё из коробки в любом современном дистрибутиве. Docker — следуй инструкции
[docs.docker.com/engine/install/](https://docs.docker.com/engine/install/).
Не забудь `sudo usermod -aG docker $USER` + перелогин, чтобы запускать без `sudo`.

#### 🪟 Windows

**Только через WSL2.** Cmd / PowerShell не поддерживаются (нет
`make` / `bash` / `openssl`, GitBash тоже частично не подходит).

1. Поставить **Docker Desktop** + включить WSL2-backend в настройках.
2. Поставить **WSL2 Ubuntu**: `wsl --install -d Ubuntu` в PowerShell от админа.
3. Перезагрузка → запустить Ubuntu → создать пользователя.
4. В Ubuntu-терминале:
   ```bash
   sudo apt update && sudo apt install -y make python3 python3-pip git curl openssl
   ```
5. Клонировать репо **внутрь WSL** (НЕ в `/mnt/c/...` — там Docker работает в 5 раз медленнее):
   ```bash
   cd ~ && git clone <repo> sqlsec && cd sqlsec
   ```
6. Дальше — как Linux.

Docker Desktop с WSL2-backend автоматически шарит сокет — `docker`/`docker compose`
работают и из Ubuntu, и из Windows-cmd одинаково.

## 1. Клонируем и поднимаем

```bash
git clone <ссылка-на-репо> sqlsec
cd sqlsec
make setup       # .env + secrets/ + Langfuse-секреты — идемпотентно
make up          # собрать образы + поднять 6 сервисов
make check       # smoke-test всего: 13 проверок, все должны быть ✔
```

Если `make check` показал все галочки — **всё работает**. Открой
http://localhost:18000 и потыкай чипы в UI.

## 2. Куда смотреть

| URL | Что |
|---|---|
| http://localhost:18000 | **главная** — поле ввода NL → SQL + audit-log |
| http://localhost:18000/docs | OpenAPI/Swagger для /audit |
| http://localhost:13000/d/sqlsec-main | Grafana дашборд «SQL Security» (admin/admin) |
| http://localhost:13001 | Langfuse трейсы (см. `docs/langfuse.md`) |
| http://localhost:19090 | Prometheus (метрики `sqlsec_*`) |
| `psql postgresql://distr_user:pass@localhost:15432/demo_db` | demo_db, 60 таблиц |

Команда `make open` напомнит этот список.

## 3. Реальная LLM (опционально)

Сразу после `make setup` система работает на **MockLLM** —
сгенерированные SQL валидные, но шаблонные. Чтобы подключить реальную LLM
(Qwen2.5-Coder-32B через OpenRouter):

```bash
# 1. Получить ключ: https://openrouter.ai/keys → Create key
echo 'sk-or-v1-XXXX' > secrets/llm_api_key   # ваш ключ → docker secret
make restart                                  # recreate app
make check                                    # должен показать реальный SQL
```

`LLM_BASE_URL` / `LLM_MODEL` уже прописаны в `.env.example` под OpenRouter +
Qwen-Coder. Если используешь другого провайдера (vLLM serve, российские) —
поменяй обе переменные в `.env`.

## 4. Langfuse трейсинг (опционально)

Подробно — [docs/langfuse.md](langfuse.md). Кратко:

```
http://localhost:13001 → войти (admin@example.com / admin1234 если БД свежая)
→ Settings → API Keys → Create
→ положить pk-lf-... и sk-lf-... в .env
→ make restart
```

После этого каждый прогон `/audit` появится во вкладке **Traces** с
длительностью и scores (`approved`, `final_risk`).

## 5. Что попробовать

- В UI клик по чипам — 6 готовых задач, от простого `COUNT(*)` до
  адверсариальных провокаций.
- `make ex-eval` — прогнать 26 тестов на точность (≥70% — порог кейса).
- `make adv-eval` — показать что calibration hints экономят 16% итераций.
- `make logs` — хвост app-логов (видно вызовы /audit, AST-парсер, embeddings).

## 6. Структура проекта

```
src/case3/
  pipeline.py                 # цикл генератор → судья → reflector
  nodes/                      # узлы пайплайна
  schema/linker.py            # schema linker (DAIL Code-Repr DDL)
  audit/                      # Phase 1 правила + multi-checker
    knowledge.py              # 15 vuln-классов с CWE/CAPEC/OWASP
    sensitive.py              # PII-паттерны (regex)
    schema_sensitive.py       # schema-grounded PII
    schema_validator.py       # ловит галлюцинации таблиц/колонок
    ast_checker.py            # pglast — точный SQL-парсер от Postgres
  llm/
    factory.py                # выбор клиента: OpenAI-compat / Colab / Mock
    embeddings.py             # bge-m3 через HF Inference + кэш на диск
  infra/
    service.py                # FastAPI: /, /audit, /healthz, /metrics
    runtime.py                # обёртка с метриками + трейсами
    metrics.py                # Prometheus-реестр (stdlib)
    tracing.py                # StubTracer + LangfuseTracer fallback
  retrieval/fewshot.py        # асимметричный few-shot (positive/negative)

deploy/
  init-db/01_schema.sql       # автозалив 60 таблиц в postgres
  seed/Dockerfile             # сидер с faker (500 строк / таблицу)
  observability/              # Prometheus + Grafana provisioning

docker-compose.yml            # 6 сервисов: db + seeder + app + prom + grafana + langfuse(+db)
Dockerfile                    # app image
Makefile                      # команды make up / check / ex-eval / ...
scripts/setup.sh              # .env + secrets/ генерация
scripts/check.sh              # smoke-test всех endpoints
docs/                         # bench, demo-сценарий защиты, ADR
```

## 7. Что обычно ломается

### `make up` падает на «port already allocated»

У тебя на хосте уже занят порт. Мы используем нестандартные:
`18000 / 19100 / 19090 / 13000 / 13001 / 15432`. Проверь:

```bash
ss -tlnp | grep -E '180|190|1300|1543'
```

Если занят какой-то — выясни кем (`docker ps` или `lsof -i :ПОРТ`),
останови, либо поправь маппинг в `docker-compose.yml`.

### `make check` показывает Langfuse 503

Langfuse инициализирует БД ~30 сек. Подожди и повтори `make check`.
Если через 2 минуты не поднялся — `docker logs sqlsec-langfuse` покажет
почему (часто — `Invalid environment variables`, см. `LANGFUSE_NEXTAUTH_SECRET`
в `.env`; сгенерировать заново: `openssl rand -base64 32`).

### `/audit` отвечает HTTP 500 с «401 Unauthorized»

В `.env` прописан `LLM_BASE_URL` (OpenRouter), но в `secrets/llm_api_key`
нет валидного ключа. Варианты:

- очистить файл: `: > secrets/llm_api_key` + `make restart` → пойдёт MockLLM
- положить настоящий ключ: `echo 'sk-or-v1-...' > secrets/llm_api_key` + `make restart`

### seeder заполнил 0 таблиц

БД ещё не успела принять подключения. Перезапусти один сервис:
```bash
docker compose up seeder
```

### Хочу всё сбросить и начать сначала

```bash
make clean       # ⚠ снесёт volume БД (данные пропадут)
make up
```

### Меняешь код Python — изменения не видны

Контейнер `app` собран один раз. После правок кода:
```bash
make restart     # пересоберёт только app
```

### macOS: `make: command not found`

Поставь Xcode Command Line Tools:
```bash
xcode-select --install
```

### macOS: всё медленно

Открой Docker Desktop → Settings → Resources → выдай **6+ ГБ RAM** и **4+ CPU**.
По умолчанию 2 ГБ маловато для Postgres + Langfuse + 4 других контейнера.

### Windows: `make: command not found` в Git Bash

GitBash не подходит — используй WSL2 (см. раздел Platform-specific).
В WSL2-Ubuntu:
```bash
sudo apt install make
```

### Windows / macOS: «cannot connect to Docker daemon»

Запусти Docker Desktop из меню Пуск/Launchpad — он должен крутиться в
системном трее. Без запущенного Desktop `docker ps` не работает.

### `make check` всё зелёное, но `/audit` тормозит (>10 сек)

Это OpenRouter — реальный LLM-вызов через интернет. Нормально 1.5-3 сек
на запрос. Если хочется быстрее для демо без сети:
```bash
: > secrets/llm_api_key && make restart   # переключение на MockLLM
```

## 8. Что прочитать дальше

- [README.md](../README.md) — общее описание системы
- [docs/bench.md](bench.md) — метрики кейса (EX 96%, 15 vuln-классов)
- [docs/demo.md](demo.md) — сценарий защиты (5 шагов через UI)
- [docs/langfuse.md](langfuse.md) — подключение трейсов
- `docs/adr/` — архитектурные решения с обоснованием
