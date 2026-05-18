# ADR-0001 — Toolchain and Python environment

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** project owner

## Context

ТЗ кейса GreenData (`tusk`, требование «Технологические требования») требует:

- Python **3.10+**.
- PostgreSQL как основная СУБД для тестирования.
- Git-репозиторий, `requirements.txt` или `pyproject.toml`.
- LLM API (OpenAI / YandexGPT / локальный) и опционально LangChain или
  аналог для RAG.

В репозитории на момент написания ADR есть:

- `baseline1.py` — скелет с типами (`@dataclass`) и контрактами. Без
  внешних зависимостей кроме stdlib.
- `data_model_sql/data_model.sql` — 657 KB DDL с 60 таблицами демо-БД
  GreenData (банк/ERP, русскоязычные `COMMENT ON`).
- `case_3.txt`, `tusk`, `take1` — описание кейса и конспект встречи с
  ментором.

На машине у разработчика:

- conda env `gpu_env` (`/home/toxic/miniconda3/envs/gpu_env`) с
  установленными `pandas`, `numpy`, `torch+cu121` и т. п. (см.
  `practicum2026/docs/adr/0001` — соседний проект).
- Системный `python3` — без нужных пакетов.

Кейс инженерный, тяжёлой ML-математики нет (`case_3.txt`: «минимум
DS-математики и упор на архитектурный дизайн агентов»). Зато нужны:
LLM SDK, парсер PostgreSQL AST, граф-фреймворк (LangGraph), векторное
хранилище для RAG, UI (Streamlit), наблюдаемость (Langfuse).

## Decision

1. **Рабочее окружение** — отдельный conda env `case3` поверх Python
   **3.11** (а не 3.12 — у части ML-библиотек, которые могут понадобиться
   для эмбеддингов, стабильнее 3.11). Активация:
   `conda activate case3`. В скриптах — абсолютный путь
   `/home/toxic/miniconda3/envs/case3/bin/python`.

2. **Зависимости** фиксируются в `pyproject.toml` (PEP 621). Базовый
   набор (детализация — в соответствующих ADR-0002…0010):

   - `langgraph`, `langchain-core`, `langchain-openai` — оркестрация
     цикла (ADR-0002).
   - `pglast` — парсер PostgreSQL AST для детерминированного аудитора
     (ADR-0004).
   - `sqlglot` — для кросс-диалектных задач и быстрого прототипирования.
   - `psycopg[binary]` — клиент Postgres (EXPLAIN, sandbox, persistence).
   - `qdrant-client` или `chromadb` — векторное хранилище для RAG
     (ADR-0005).
   - `sentence-transformers` + модель `intfloat/multilingual-e5-large`
     для русскоязычных эмбеддингов схемы и вопросов.
   - `langfuse` — observability (ADR-0009).
   - `streamlit`, `streamlit-ace` — демо (ADR будет отдельный).
   - `pytest`, `pytest-postgresql`, `alembic`, `faker` — тестовая
     песочница (ADR-0004).
   - `pandas`, `numpy` — аналитика и отчёты по метрикам.

3. **Postgres для разработки и тестов** — Docker Compose, `postgres:17`
   c `tmpfs: /var/lib/postgresql/data`, `fsync=off`,
   `synchronous_commit=off` в тестовой конфигурации. Сидинг — через
   `data_model_sql/data_model.sql` + `faker` для синтетических строк
   (детали — ADR-0004).

4. **Структура репозитория** (создаётся постепенно):

   ```
   .
   ├── baseline1.py                # уже есть (контракты)
   ├── case_3.txt, tusk, take1     # уже есть (ТЗ + конспект)
   ├── data_model_sql/             # уже есть (DDL GreenData)
   ├── research/                   # уже есть (5 кругов лит-обзора)
   ├── docs/adr/                   # этот журнал
   ├── pyproject.toml              # появится с первым кодом
   ├── src/case3/                  # код пакета (generator, auditor, loop, …)
   ├── tests/
   ├── notebooks/                  # эксперименты по требованиям ТЗ
   ├── data/                       # синтезированный датасет (gitignored)
   ├── compose/                    # docker-compose, dockerfiles
   └── ui/                         # Streamlit-приложение
   ```

5. **Git workflow** — ветка `master` под trunk; крупные изменения —
   через feature-ветки с PR. Коммиты «по делу», без длинных
   английских formality-сообщений.

## Consequences

**Положительные**

- Старт с пустого env гарантирует отсутствие unrelated-зависимостей
  (gpu_env у соседнего кейса завязан на CUDA, нам это не нужно).
- `pyproject.toml` поверх conda даёт воспроизводимость по требованию
  заказчика без переезда на Poetry/uv (для MVP это лишний слой).
- Все ключевые библиотеки — Apache 2.0 / MIT, можно показать заказчику
  без лицензионных вопросов (важно: `pglast` — GPLv3, см.
  *Consequences → Риски*).
- `tmpfs` + `fsync=off` в тестовом Postgres даёт x3-x5 к скорости CI.

**Отрицательные / Риски**

- **`pglast` — GPLv3**. Если интеграция в платформу GreenData
  потребует не-GPL лицензии, надо переходить на `sqlglot` (MIT) с
  потерей точности парсинга PL/pgSQL. Решение фиксируется отдельным
  ADR при необходимости.
- Список зависимостей крупный — будет долгая первая установка
  (`sentence-transformers` ставит `torch`, ~2 GB). Для CI кешируем
  layer.
- LangGraph до сих пор быстро ломает API между минорами; pin-ить
  жёстко (`langgraph==0.2.x`) и поднимать вместе с тестами.

## Alternatives considered

| Альтернатива | Почему отказались |
|---|---|
| Один большой `gpu_env` на оба кейса (case_3 и case_4) | Кейсы независимые, версии зависимостей конфликтуют. Изоляция дешевле, чем разруливать конфликты позже. |
| Голый venv + `pip` без conda | conda проще ставит system-deps под `psycopg`, `faiss`, `sentence-transformers`. На Linux разницы немного, но conda унификация с соседним кейсом. |
| Poetry / uv | На MVP — лишний слой. Перейдём, если в команде > 2 человек или появится монорепо. |
| SQLite вместо PostgreSQL для тестов | ТЗ: «Диалект только PostgreSQL (обязательно)». PL/pgSQL и `EXPLAIN (FORMAT JSON)` в SQLite физически невозможны. |
| Полный отказ от LangGraph (своя state machine) | Своя FSM пишется за день, но теряем встроенные checkpointers, persistence и интеграцию с Langfuse. Эти возможности нужны по ADR-0009. |

## Links

- ТЗ: `tusk` § «Технологические требования»
- Скелет с контрактами: `baseline1.py`
- DDL GreenData: `data_model_sql/data_model.sql`
- Соседний кейс (стиль ADR): `practicum2026/docs/adr/0001-toolchain-and-environment.md`
- Зависимости детально: ADR-0002 (LangGraph), ADR-0004 (pglast),
  ADR-0005 (Qdrant), ADR-0009 (Langfuse)
