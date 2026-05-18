# Круг 3 — Детерминированные SQL-валидаторы (слой быстрых правил)

Цель: ловить базовые уязвимости **без LLM** (скорость + аудируемость), а LLM-судья работает поверх findings.

## 1. Парсеры PostgreSQL AST для Python

### `pglast` (обёртка над libpg_query) ⭐
- https://pypi.org/project/pglast/
- https://pglast.readthedocs.io/en/latest/visitors.html
- Тот же C-парсер, что и сам PostgreSQL → AST бит-в-бит соответствует реальному.
- Активно поддерживается (master = PG18, ветки v3–v8).
- **Ключевые функции**: `parse_sql()` и `parse_plpgsql()` (редкость среди парсеров).
- API: дерево из `Node`/`List`/`Scalar`, каждый узел `tag` + атрибуты.
- `pglast.visitors.Visitor` — visitor-паттерн с BFS-обходом и методами `visit_XYZ(self, ancestors, node)`. Может вернуть замену → удобно и для проверок, и для переписывания.
- **Это лучший выбор для аудитора.**

### `sqlglot`
- https://github.com/tobymao/sqlglot
- Чистый Python, 31 диалект (`dialect="postgres"`).
- API: `parse_one(sql).find_all(exp.Update)`, `.transform()`.
- **PL/pgSQL не поддерживается.**
- Часть PG-специфики (`DO $$...$$`, `RAISE`, `PERFORM`) парсится хуже.

### `psqlparse`
- Устаревшая обёртка. **Не брать.**

## 2. Линтеры

### `sqlfluff`
- https://docs.sqlfluff.com/en/stable/reference/rules.html
- Полезные встроенные правила:
  - **AM04** (`ambiguous.column_count`) — ловит `SELECT *`.
  - **AM08** (`ambiguous.join_condition`) — неявные cross join.
  - **AM09** (`ambiguous.order_by_limit`) — `LIMIT` без `ORDER BY`.
  - **CV12** — джойн через WHERE вместо ON.
  - **ST03/ST11** — неиспользуемые CTE/JOIN.
- **Чего нет из коробки**: `UPDATE/DELETE без WHERE` и `отсутствие LIMIT в SELECT`. Можно писать кастомные правила (наследник `BaseRule`), но **дешевле сделать на pglast**.

### `pgsanity`
- https://github.com/markdrago/pgsanity
- Только синтаксическая проверка через `ecpg`. Полузаброшен.
- Лучше использовать `pglast.parser.parse_sql()` — бросает исключение на невалидном SQL.

## 3. Готовые статанализаторы на инъекции

### `semgrep` ⭐
- https://semgrep.dev/p/sql-injection
- https://semgrep.dev/docs/learn/vulnerabilities/sql-injection
- Регистр `p/sql-injection` + `p/owasp-top-ten` + `p/security-audit`.
- Паттерн-матчит по AST исходного кода (Python/Java/JS/Go).
- Ловит конкатенацию пользовательского ввода: f-strings, `%`, `.format()`, `+`.
- Поддерживает `pattern-either` и **taint-tracking** (source→sink).
- **Must have для хакатона.**

### `CodeQL`
- https://codeql.github.com/codeql-query-help/python/py-nosql-injection/
- Полноценный dataflow + taint-tracking через `DataFlow::Configuration`.
- Мощнее, но требует сборки базы. Для MVP за неделю избыточен.

### `sql-lint` (joereynolds)
- Полузаброшен; умеет DELETE без WHERE, но слабее своей реализации на pglast.

### `squabble`
- https://github.com/erik/squabble
- Линтер для миграций (рискованные DDL). Хорош как референс паттернов.

### `plpgsql_check` ⭐
- https://github.com/okbob/plpgsql_check
- Расширение PostgreSQL — статанализатор PL/pgSQL.
- Ловит: обращение к несуществующим колонкам, мёртвый код, переменные в `EXECUTE`, mismatched return types.
- **Закрывает бонус +10 за PL/pgSQL.**

## 4. EXPLAIN (FORMAT JSON) — детект тяжёлых операций

`EXPLAIN (FORMAT JSON) <query>` → JSON-дерево `Plan`:
- `Node Type`, `Relation Name`, `Startup Cost`, `Total Cost`, `Plan Rows`, `Plan Width`, рекурсивный `Plans`.

**Что искать обходом дерева:**
- `Node Type == "Seq Scan"` + `Plan Rows > 10000` → нет индекса по WHERE.
- `Node Type == "Nested Loop"` без `Join Filter`/`Hash Cond`/`Index Cond` → cartesian product. Альт: `rows_out > rows_left * rows_right * 0.5`.
- Высокий `Total Cost`: warning `>10000`, error `>100000`.
- `Plan Rows` сильно расходится с реальностью — устаревшая статистика (только при `EXPLAIN ANALYZE`).

**Cost-параметры по умолчанию**: `seq_page_cost=1.0`, `random_page_cost=4.0`, `cpu_tuple_cost=0.01`. Калибровать на железе или нормализовать на `Plan Rows / pg_class.reltuples`.

**Важно:**
- `EXPLAIN` без `ANALYZE` не исполняет запрос — безопасно гонять в CI.
- **`EXPLAIN ANALYZE` на UPDATE/DELETE/INSERT реально применяется!** Нужно `BEGIN; EXPLAIN ANALYZE ...; ROLLBACK;`.

Источники:
- https://www.postgresql.org/docs/current/using-explain.html
- https://scalegrid.io/blog/postgres-explain-cost/
- https://www.crunchydata.com/blog/postgres-scan-types-in-explain-plans

## 5. Песочница без данных (Docker + Alembic)

Best practices для CI:

1. **Docker Compose с healthcheck**: `depends_on: condition: service_healthy` + `pg_isready` в healthcheck.
2. **`alembic check`** (≥1.9) в PR-пайплайне — падает, если модели не отражены в миграциях.
3. **Двойная сборка схемы**: `Base.metadata.create_all()` vs прогон миграций; diff на `pg_dump --schema-only`.
4. **tmpfs для тестовой БД**: `tmpfs: /var/lib/postgresql/data` — БД в RAM.
5. **`fsync=off`, `synchronous_commit=off`** в тестовом Postgres — x3-x5 к скорости.

**Для dry-run EXPLAIN без коннекта к проду**: контейнер с прогнанными миграциями, минимальный синтетический набор через faker. Запускать `EXPLAIN` (без ANALYZE) внутри транзакции с `ROLLBACK`.

**Pure-Python**: pglast валидирует синтаксис и таблицы/колонки, но не даёт cost-оценок.

## 6. Детект чувствительных колонок

### Microsoft Presidio ⭐
- https://github.com/microsoft/presidio
- https://microsoft.github.io/presidio/tutorial/02_regex/
- `PatternRecognizer` (regex + контекст + валидация Луна).
- Из коробки: CREDIT_CARD, EMAIL, IBAN, PHONE, US_SSN, US_PASSPORT, US_DRIVER_LICENSE, IP.
- Регексы под Apache 2.0 — можно вытащить.

### Piiranha (HuggingFace)
- `iiiorg/piiranha-v1` — NER на 17 классов PII, 6 языков.
- Для MVP избыточно.

### DataHub PII classifier
- yaml-конфиги с regex на имена колонок: `password|passwd|pwd|secret|token|api_key|ssn|passport|card_number|cc_num|cvv`.

### AWS Glue / Comprehend — закрытый список как референс.

**Прагматичный MVP-словарь** для `information_schema.columns`:
```
password|passwd|pwd|secret|api[_-]?key|token|access[_-]?token
ssn|social[_-]?security
passport|inn|snils
card[_-]?(number|num|no)|pan|cvv|cvc
email|phone|mobile
dob|birth(_?date|day)
```

## Минимальный набор для MVP за неделю

**Ядро аудитора (1-2 дня):**
1. **`pglast`** + свои Visitor-правила:
   - `SELECT *` → ищем `A_Star` в targetList.
   - `UPDATE/DELETE без WHERE` → нет `whereClause` в `UpdateStmt`/`DeleteStmt`.
   - Нет `LIMIT` → нет `limitCount` в `SelectStmt`.
   - `EXECUTE` с конкатенацией → `ExecuteStmt` с `A_Expr` op `||`.
   - `SECURITY DEFINER` без `SET search_path` → атрибут `CreateFunctionStmt`.

**Инъекции в host-коде (1 день):**
2. **`semgrep` + `p/sql-injection` + `p/python.django` / `p/python.flask`**.

**Производительность (1-2 дня):**
3. **`EXPLAIN (FORMAT JSON)`** через psycopg к Docker-контейнеру. Обход на Python: Seq Scan + Plan Rows, Nested Loop без условий, Total Cost > порога.

**Песочница (0.5 дня):**
4. **Docker Compose + Alembic** с tmpfs, faker для синтетических данных.

**Чувствительные колонки (0.5 дня):**
5. ~30 regex-паттернов + сверка с `information_schema.columns`.

**Не брать**: CodeQL (тяжёлый), sqlfluff кастомные плагины (дублирует pglast), pgsanity (слаб), psqlparse (мёртв), Piiranha/Presidio NER (избыточно). `plpgsql_check` — опционально для бонуса.

## Архитектурный совет

Каждая проверка — отдельный `Visitor`-класс, возвращающий `list[Finding(rule_id, severity, location, snippet, message)]`. **LLM-судья работает поверх Findings в стадии «триаж»** — отсеивает false positives и приоритизирует. Так детерминированная часть остаётся быстрой и аудируемой, а LLM добавляет качества на нюансных случаях.

## Источники

- [pglast on PyPI](https://pypi.org/project/pglast/)
- [pglast visitors documentation](https://pglast.readthedocs.io/en/latest/visitors.html)
- [pglast parser documentation](https://pglast.readthedocs.io/en/stable/parser.html)
- [SQLGlot GitHub](https://github.com/tobymao/sqlglot)
- [Top Open-Source SQL Parsers 2025 — Bytebase](https://www.bytebase.com/blog/top-open-source-sql-parsers/)
- [SQLFluff Rules Reference](https://docs.sqlfluff.com/en/stable/reference/rules.html)
- [pgsanity GitHub](https://github.com/markdrago/pgsanity)
- [plpgsql_check GitHub](https://github.com/okbob/plpgsql_check)
- [Semgrep SQL Injection ruleset](https://semgrep.dev/p/sql-injection)
- [CodeQL Python SQL Injection](https://codeql.github.com/codeql-query-help/python/py-nosql-injection/)
- [sql-lint GitHub](https://github.com/joereynolds/sql-lint)
- [squabble](https://github.com/erik/squabble)
- [PostgreSQL Using EXPLAIN docs](https://www.postgresql.org/docs/current/using-explain.html)
- [Postgres EXPLAIN cost — ScaleGrid](https://scalegrid.io/blog/postgres-explain-cost/)
- [Postgres Scan Types — Crunchy Data](https://www.crunchydata.com/blog/postgres-scan-types-in-explain-plans)
- [Alembic в CI/CD — StackLesson](https://www.stacklesson.com/react-fastapi/fastapi-alembic/ch25-lesson-05-alembic-in-ci-cd/)
- [FastAPI + Alembic + Docker — Berk Karaal](https://berkkaraal.com/blog/2024/09/19/setup-fastapi-project-with-async-sqlalchemy-2-alembic-postgresql-and-docker/)
- [Microsoft Presidio GitHub](https://github.com/microsoft/presidio)
- [Presidio regex recognizers](https://microsoft.github.io/presidio/tutorial/02_regex/)
- [Piiranha-v1 on HuggingFace](https://huggingface.co/iiiorg/piiranha-v1-detect-personal-information)
- [Netwrix — Regex for sensitive data](https://netwrix.com/en/resources/blog/regular-expressions-for-beginners-how-to-get-started-discovering-sensitive-data/)
- [Strac — Catalog of Sensitive Data Elements](https://www.strac.io/blog/strac-catalog-of-sensitive-data-elements)
