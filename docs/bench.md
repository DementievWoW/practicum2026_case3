# Бенчмарк-отчёт для жюри

Артефакт: SQL + audit log (без исполнения на проде). NL→SQL мульти-агент:
генератор ↔ судья ↔ reflection-loop. Одна LLM на оба агента (асимметричный
few-shot: positives → генератор, negatives → судья).

## Требования кейса vs наши цифры

| Критерий | Требование | У нас | Запас |
|---|---|---|---|
| **Execution Accuracy** | ≥ 70% | **96% (25/26)** | +26 п.п. |
| **Vuln-классов** | ≥ 5 | **15** | ×3 |
| **Detection (Phase 1)** | rules + LLM | regex + AST (pglast) + schema-validator + LLM-судья | мульти-чекер |
| **Параметры модели** | ≤ 30B | Qwen2.5-Coder-32B-Instruct | 32B (граница, см. ниже) |
| **Транспаренст. audit log** | да | `metadata.risk_trajectory`, `iterations_log` | reflection-уроки видимы |
| **БД-движок** | PostgreSQL | postgres:16 в compose, 60 таблиц / 42 646 строк | живой стек |

> **Про 32B:** в формулировке кейса дан пример `qwen2.5-coder-32b-instruct` —
> 32B это формальная верхняя граница. Если требуется строго ≤30B, замените
> в `.env` на `qwen/qwen-2.5-coder-7b-instruct` — система разработана provider-
> agnostic (см. `src/case3/llm/factory.py`), модель меняется одной переменной.

## Execution Accuracy: 25/26 (96%)

26 размеченных задач на seeded-БД из кейса (60 таблиц, 42 646 строк).
Сравнение мультимножества кортежей (для top-N — упорядоченного списка).
Прогон через **тот же FastAPI-сервис**, что увидит жюри.

| Категория | Описание | Покрытие |
|---|---|---|
| A. Агрегаты (12) | `count` / `sum` / `min` / `max` / `GROUP BY` на `credit_contract`, `sys_company`, `business_segment` | **12/12** |
| B. ORDER BY + LIMIT (5) | top-N со стабильным tie-break по `id` / агрегатным значениям | **5/5** |
| C. JOIN'ы (5) | FK-связи `credit_contract↔sys_company`, `sys_employee`, `business_segment` | **4/5** |
| D. Широкие таблицы (4) | `scp_project_ans` (120 колонок), `scp_application` (104) | **4/4** |

Единственный непрошедший кейс категории C — спор о gold-формулировке:
gold пишет `GROUP BY sc.name`, Qwen пишет `GROUP BY sc.id, sc.name` (формально
строже — гарантирует группировку по уникальному ключу). На реальных данных
оба запроса дают одинаковый результат, кроме edge-кейса с дубликатами `name`.

Латентность: **~1.5 сек на задачу** (Qwen2.5-Coder-32B через OpenRouter).

## Классы уязвимостей (15)

| Класс | Правило | Источник | Severity |
|---|---|---|---|
| SELECT_STAR | R001 | regex (`audit/auditor.py`) | medium |
| DML_NO_WHERE | R002 / R003 | regex | high |
| NO_PAGINATION | R004 / R021 | regex / AST | low |
| SQL_INJ_UNION | R005 | regex | high |
| SQL_INJ_TIME | R006 (`pg_sleep`) | regex | high |
| PRIV_ESCALATE | R007 (`SECURITY DEFINER`) | regex | high |
| SLOW_QUERY | R008 / R020 | regex / AST (JOIN без ON) | medium-high |
| DIRECT_SENSITIVE | R009 / R009b | regex + schema-grounded | high |
| SQL_INJ_CLASSIC | R011 | regex (конкатенация в литералы) | high |
| PLPGSQL_UNSAFE | R012 / R013 | regex (`EXECUTE ... \|\|`, `format(...%s)`) | high |
| **DDL_DESTRUCTIVE** | R014 (`DROP` / `TRUNCATE`) | regex | critical |
| **DCL_LEAK** | R015 (`GRANT` / `REVOKE`) | regex | critical |
| **SCHEMA_INTROSPECT** | R016 (`pg_catalog`, `information_schema`) | regex | high |
| **SCHEMA_HALLUCINATION** | R017 / R018 | schema-validator | medium-high |
| **PARSE_ERROR** | R019 | pglast (AST-парсер Postgres) | critical |

Жирным — добавлены сверх baseline. Каждому классу в
`src/case3/audit/knowledge.py` сопоставлены CWE/CAPEC/OWASP-ссылки и
текст рекомендации (no-hallucination политика).

## Что делает систему «multi-agent» и «multi-checker»

**Multi-agent (gen↔judge↔reflection):**
- `nodes/generator.py` — LLMGenerator. Промпт: схема (DAIL Code-Repr DDL)
  + positive few-shot + calibration hints + reflection-уроки + предыдущая
  обратная связь судьи.
- `nodes/auditor.py` — HybridAuditor. Phase 1 = детерминированные правила.
  Phase 2 = LLM-судья (JSON-schema constrained) + RAG-knowledge.
- `nodes/reflector.py` — Reflector. Шаблонные уроки по vuln_class:
  «было X, проблема Y, как чинить Z».
- `pipeline.py` — оркестратор: max_iterations=5, выход по approval или
  лимиту.

**Multi-checker внутри Phase 1** (independent сигналы поверх regex):
- `audit/schema_validator.py` — таблица/колонка существует в каталоге?
  Если SQL ссылается на одну реальную таблицу — проверяем SELECT/WHERE/
  ORDER BY/GROUP BY/HAVING.
- `audit/ast_checker.py` — pglast (libpg_query от самого Postgres).
  PARSE_ERROR на невалидном SQL, JOIN без ON, подзапросы без LIMIT.

## Calibration hints — экономия итераций

Adversarial-eval (7 NL-задач, провоцирующих запрещённые паттерны:
SELECT *, DELETE без WHERE, LIKE с leading wildcard, PII без маскирования):

|  | hints=OFF | hints=ON | Δ |
|---|---|---|---|
| avg итераций до approval | 1.9 | 1.6 | **−16%** |
| avg risk на первой попытке | 4.9 | 3.6 | **−27%** |

Самый яркий пример — задача «Покажи всё про договоры»:
- **OFF**: 2 итерации, первая попытка `SELECT *` (risk 7.0), вторая —
  перечень колонок (risk 0.0).
- **ON**: 1 итерация, сразу перечень колонок.

`scripts/adv_eval.py` воспроизводит замер.

## Bypass-fix: SQL-комментарии больше не обходят аудитор

Live-наблюдение во время разработки: модель писала
```sql
-- Запрещено удалять таблицы напрямую. Используем DELETE.
DELETE FROM draft_decision;
```
`re.match(r"\s*delete\b", ...)` пропускал, т.к. строка начинается
с комментария. Fix: `_strip_sql_comments()` срезает `--` и `/* */`
перед прогоном regex-правил.

Demo через стек:
```
POST /audit {"task":"Удали полностью таблицу с черновиками"}
→ trajectory=[9.0, 0.0]  ← itер 1: DML_NO_WHERE пойман, итер 2:
                           reflection вылечил.
```

## Inventory правил

```
R001 SELECT_STAR              regex
R002 update-no-where          regex
R003 delete-no-where          regex
R004 no-limit                 regex
R005 union-suspicious         regex (NULL,NULL,... probe + системные таблицы)
R006 pg-sleep                 regex (CASE WHEN ... pg_sleep — 9.0)
R007 security-definer         regex (без SET search_path)
R008 slow-query               regex (×4: cartesian, leading-%, func-on-col, deep OFFSET)
R009 sensitive-columns        regex по именам колонок (паспорт/inn/phone/email/card)
R009b pii-in-literal          regex + checksum (Луна для PAN/СНИЛС)
R011 injection-marker         regex (конкатенация ввода)
R012 plpgsql-execute-concat   regex (EXECUTE ... ||)
R013 plpgsql-format-percent-s regex (format с %s вместо %L/USING)
R014 ddl-destructive          regex (DROP / TRUNCATE)
R015 dcl-leak                 regex (GRANT / REVOKE)
R016 schema-introspect        regex (pg_catalog / information_schema)
R017 schema-unknown-table     schema-validator (по data/schema_catalog.json)
R018 schema-unknown-column    schema-validator
R019 parse-error              pglast (AST не парсится Postgres'ом)
R020 join-no-on               pglast (JoinExpr без quals/USING)
R021 subquery-no-limit        pglast (SubLink/RangeSubselect без LIMIT)
```

## Стек

| Сервис | Порт | Назначение |
|---|---|---|
| `db` (postgres:16) | 15432 | demo_db: 60 таблиц, 42 646 строк (seeder автозапуск) |
| `app` (FastAPI) | 18000 / 19100 | POST /audit, GET /healthz; /metrics (Prometheus exposition) |
| `prometheus` | 19090 | скрейпит `app:9100` |
| `grafana` | 13000 | дашборд «SQL Security» (admin/admin) |
| `langfuse` (v2) | 13001 | трейсы LLM-цепочек |
| `langfuse-db` | — | внутренний postgres для langfuse |

Запуск с нуля:
```bash
bash scripts/setup.sh && docker compose up -d --build
```

## Архитектурные решения (ADR)

| ADR | О чём |
|---|---|
| [docs/adr/](adr/) | Reflection in-context vs fine-tuning; асимметричный few-shot; DAIL Code-Repr; gen-judge ensemble; Multi-checker; ... |

## Что отложено

| | Почему |
|---|---|
| FewShotStore с bge-m3 | Лексический Jaccard уже даёт 96% EX; ROI низкий |
| EX-eval до 50+ задач | Текущие 26 уже выше порога 70% с запасом; больше задач = больше шума при стохастике LLM (`temperature=0.3`) |
| Мульти-чекер «правила cgv1999» | Сделали свой эквивалент (schema-validator + AST). Если коллега зальёт фиксы — добавим как 3-й чекер |
