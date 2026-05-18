# 06 — PL/pgSQL: небезопасный EXECUTE

- **`vuln_class`:** `PLPGSQL_UNSAFE`
- **Риск:** 9/10
- **CWE:** [CWE-89 — Improper Neutralization in SQL](https://cwe.mitre.org/data/definitions/89.html) (вариант для процедурного языка).
- **CAPEC:** [CAPEC-66 — SQL Injection](https://capec.mitre.org/data/definitions/66.html).
- **Бонусный класс ТЗ** (+10 баллов), см. ADR-0010.

## Что

В теле функции на PL/pgSQL используется оператор **`EXECUTE`** с динамически построенной строкой запроса, где параметры вкатываются через конкатенацию (`||`) или через `format()` без подстановки `USING`. Это PL/pgSQL-эквивалент классической SQL-инъекции (`SQL_INJ_CLASSIC`), но опаснее: внутри `SECURITY DEFINER`-функции эксплуатация даёт ещё и privilege escalation (см. [05](../05-privilege-escalation-execute/)).

Каноническое предупреждение: [PostgreSQL docs § Executing Dynamic Commands](https://www.postgresql.org/docs/current/plpgsql-statements.html#PLPGSQL-STATEMENTS-EXECUTING-DYN).

## Почему опасно (риск 9)

- **Эквивалент SQLi** — атакующий через переданный параметр выполняет произвольный SQL.
- **Часто внутри `SECURITY DEFINER`** — двойной удар: SQLi + privilege escalation.
- **Затрагивает аналитические функции и stored procedures** — часть бизнес-логики GreenData, поэтому критично для заказчика.

Риск 9 (на ступень ниже 10 у host-кода) — потому что доступ к PL/pgSQL функциям обычно ограничен ролью, тогда как host-код обрабатывает любой пользовательский ввод напрямую.

## PostgreSQL specifics

PL/pgSQL даёт **три способа динамического SQL**, два безопасных:

| Способ | Безопасность | Когда применять |
|---|---|---|
| `EXECUTE 'SELECT ... WHERE x = ' \|\| param` | ❌ инъекция | Никогда |
| `EXECUTE 'SELECT ... WHERE x = $1' USING param` | ✅ параметризация | Литералы (значения) |
| `EXECUTE format('SELECT ... WHERE x = %L', param)` | ✅ при правильном `%L`/`%I` | Только если `USING` неудобен |
| `EXECUTE format('SELECT ... FROM %I WHERE x = $1', tbl) USING param` | ✅ комбо | Имя таблицы + значение |

**Спецификаторы `format()`:**
- `%L` — литерал (эквивалент `quote_nullable`).
- `%I` — идентификатор (эквивалент `quote_ident`).
- `%s` — **сырая подстановка, НЕ безопасна** (эквивалент `||`).

**Подводный камень:** `format(..., %s, param)` синтаксически выглядит как параметризация, но фактически = `||`. Это часто принимают за безопасный паттерн.

## Пример антипаттерна

```sql
-- УЯЗВИМО: конкатенация через ||
CREATE OR REPLACE FUNCTION find_user(login text)
RETURNS SETOF users
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY EXECUTE 'SELECT * FROM users WHERE login = ''' || login || '''';
END;
$$;
```

```sql
-- УЯЗВИМО: format() с %s
CREATE OR REPLACE FUNCTION find_user(login text)
RETURNS SETOF users
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY EXECUTE format('SELECT * FROM users WHERE login = %s', login);
    --                                                              ^^^ %s, а не %L
END;
$$;
```

Payload `login = "admin'' OR ''1''=''1' --"` сработает обоими способами.

## Внешние ссылки

- **CWE-89**, **CAPEC-66** — в шапке.
- **PG docs PL/pgSQL** — https://www.postgresql.org/docs/current/plpgsql-statements.html#PLPGSQL-STATEMENTS-EXECUTING-DYN
- **`plpgsql_check`** — https://github.com/okbob/plpgsql_check
- **research/05_peripheral.md** § 6 — EPAM Code Migration, SQLGenie (executor как оракул).

## Варианты решения

См. [solutions.md](solutions.md).
