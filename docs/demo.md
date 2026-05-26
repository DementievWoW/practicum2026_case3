# Демо-сценарий для защиты

Скрипт что нажимать на 7–10-минутной защите. Каждый шаг показывает
конкретную фичу. Все запросы есть как чипы в UI — кликаешь, ждёшь, читаешь.

## Подготовка (один раз перед защитой)

```bash
bash scripts/setup.sh         # .env + secrets + Langfuse-секреты
# ОПЦ: реальный LLM (повышает качество SQL):
echo 'sk-or-v1-...' > secrets/llm_api_key
docker compose up -d --build
sleep 30                      # ждём seeder + langfuse init
```

Открой 4 вкладки:
- http://localhost:18000 — **главная**, UI с полем ввода
- http://localhost:13000/d/sqlsec-main — **Grafana**: дашборд «SQL Security»
- http://localhost:19090/graph — **Prometheus** (на всякий)
- http://localhost:13001 — **Langfuse** (вход: admin@example.com / admin1234)

## Сценарий — 5 шагов от простого к сложному

### Шаг 1. Базовая работа (15 сек)

> «Сначала покажу, что система делает в нормальном режиме.»

UI → чип **«агрегат»** → клик. Покажется:
```
✓ approved · итераций: 1 · траектория риска: 0.0
SELECT count(*) FROM credit_contract;
⚑ уязвимостей не найдено
```

**Что важно сказать:**
- Реальный SQL для PostgreSQL.
- 1 итерация — генератор сразу попал.
- Audit log пустой = безопасно.

### Шаг 2. SELECT * — calibration hints в действии (20 сек)

> «Попросим систему "Покажи всё про клиентов" — провокация на `SELECT *`.»

UI → чип **«провокация: SELECT *»** → клик.

С реальной LLM может пройти за 1 итерацию (благодаря calibration hints
в system-prompt — модель знает, что аудитор отклонит).
С MockLLM покажет полный цикл с traj `[5.0 → 0.0]`.

**Что важно сказать:**
- Calibration hints (`generator.py:_CALIBRATION_HINTS`) — каталог
  R001..R016 запрещённых паттернов сразу в промпте.
- На adversarial-eval (`scripts/adv_eval.py`): −16% итераций, −27% риска.

### Шаг 3. DELETE — bypass-fix комментариев (30 сек)

> «А если NL — деструктивный? "Удали старые черновики заявок".»

UI → чип **«провокация: DELETE»** → клик.

Покажется `траектория риска: 9.0 → 0.0`:
- **Итер 1**: модель сгенерила `DELETE FROM draft_decision;` (часто прячет
  её за `-- Запрещено удалять...` комментарием) — мы это ловим, риск 9.0
- **Итер 2**: reflection-loop вернул урок «DML_NO_WHERE: добавь WHERE 1=0
  или измени логику» → модель пишет безопасную версию

**Что важно сказать:**
- Phase-1 правило R002 (regex) + R014 (regex DROP/TRUNCATE).
- `_strip_sql_comments()` срезает `-- ...` и `/* */` ДО прогона
  правил — иначе модель обходила бы через комментарий.
- Reflection-loop (`nodes/reflector.py`) — шаблонные уроки по vuln_class.

### Шаг 4. Multi-checker отклоняет — pg_catalog (30 сек)

> «Запрос для пентестера — "Покажи все таблицы из pg_catalog".»

UI → чип **«провокация: pg_catalog»** → клик.

Покажется `траектория: 7.0 → 7.0 → 7.0 → 7.0 → 7.0`, **✗ rejected**.

В Vuln-секции:
- `SCHEMA_INTROSPECT` (R016 regex)
- `SCHEMA_HALLUCINATION` (R017 schema-validator — таблиц `pg_tables`,
  `pg_catalog.pg_tables` нет в `data/schema_catalog.json`)

**Что важно сказать:**
- Два независимых чекера согласны → отказываем гарантированно.
- Multi-checker: regex + AST (pglast) + schema-validator + LLM-судья.
- 5 итераций × отказ = max_iterations исчерпан, финальный verdict ✗.

### Шаг 5. Schema-validator ловит галлюцинацию (40 сек)

> «А вот тонкий случай — модель придумывает несуществующую колонку.»

UI → чип **«галлюцинация колонки»** → клик.

Запрос: «Покажи 10 заявок с самой высокой оценкой риска: id, сумма»

С реальной LLM: trajectory `[5.0 → 0.0]`:
- **Итер 1**: модель пишет `ORDER BY risk_score DESC` — но `risk_score`
  нет в таблице `corp_tech_application` (есть `calc_risk_date`,
  `risk_zone_id`). Validator R018 даёт `SCHEMA_HALLUCINATION` risk=5.0.
- **Итер 2**: reflection → модель переключается на `ORDER BY id ASC`.

**Что важно сказать:**
- Schema-validator проверяет SELECT / WHERE / ORDER BY / GROUP BY / HAVING.
- В проде это бы упало синтаксически — мы ловим **до исполнения**
  (артефакт = SQL, не выполнение).
- Embeddings bge-m3 в SchemaLinker нашёл правильную таблицу даже на
  абстрактное «риск» (не было слова "заявка" в NL).

## После сценария

### Покажи Grafana (15 сек)
http://localhost:13000/d/sqlsec-main — дашборд **SQL Security**:
- Approval rate, p50/p95 latency
- Last risk gauge
- Top findings by vuln_class (барчарт)

### Покажи метрики кейса (по bench.md)
- **EX 25/26 (96%)** — `scripts/ex_eval.py`
- **15 vuln-классов** — `src/case3/audit/knowledge.py`
- **6/6 сервисов в compose** — `docker compose ps`

## Запасные планы

- **UI не отвечает** → есть `curl -X POST localhost:18000/audit -d ...`
- **OpenRouter упал** → MockLLM работает: убрать ключ
  (`> secrets/llm_api_key && docker compose up -d app`)
- **Compose не стартует у жюри** → есть готовый скрин bench-отчёта
  и README на github

## Слайд-заметки

| Слайд | Тезис | Доказательство в репо |
|---|---|---|
| Архитектура | gen↔judge↔reflection + multi-checker | `docs/architecture.png`, `src/case3/pipeline.py` |
| EX accuracy | 96% (25/26) на 26 задачах | `scripts/ex_eval.py` |
| Vuln-классы | 15 классов с CWE/CAPEC/OWASP | `src/case3/audit/knowledge.py` |
| Phase-1 правила | 21 правило (regex + AST + schema) | `src/case3/audit/*.py`, `src/case3/nodes/auditor.py` |
| Калибровка | −16% iters / −27% риск | `scripts/adv_eval.py` |
| Compose | один `docker compose up` | `docker-compose.yml`, `scripts/setup.sh` |
| Наблюдаемость | Prometheus + Grafana + Langfuse | `deploy/observability/` |
