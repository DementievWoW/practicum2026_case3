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

**Подводный камень:** `format(..., %s, param)` синтаксически выглядит как параметризация, но фактически = `||`. Это часто принимают за безопасный паттерн. Phase 1 правило должно его отделять.

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

## Эталонный fix

**Вариант 1 — параметризация через `USING`:**
```sql
CREATE OR REPLACE FUNCTION find_user(login text)
RETURNS SETOF users
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY EXECUTE 'SELECT * FROM users WHERE login = $1' USING login;
END;
$$;
```

**Вариант 2 — `format()` с `%L`:**
```sql
RETURN QUERY EXECUTE format('SELECT * FROM users WHERE login = %L', login);
```

**Вариант 3 — комбо для динамического идентификатора:**
```sql
CREATE OR REPLACE FUNCTION dyn_select(tbl text, key text)
RETURNS SETOF record
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY EXECUTE format('SELECT * FROM %I WHERE id = $1', tbl) USING key;
END;
$$;
```

При наличии `SECURITY DEFINER` — обязательно добавить `SET search_path` (см. [05](../05-privilege-escalation-execute/)).

## Как мы детектим

### Phase 1 — два правила (ADR-0004 + ADR-0010)

**`R012-plpgsql-execute-concat`:**
```python
class PlpgsqlExecuteConcat(Visitor):
    def visit_ExecuteStmt(self, ancestors, node):  # внутри parse_plpgsql
        # node.query — выражение, переданное в EXECUTE
        if is_string_concat(node.query):  # A_Expr op '||' с переменной
            yield Finding(
                rule_id="R012-plpgsql-execute-concat",
                vuln_class="PLPGSQL_UNSAFE",
                severity="high", risk_score=8,
                message="EXECUTE с конкатенацией через ||",
            )
```

**`R013-plpgsql-format-without-using`:**
```python
def visit_FuncCall(self, ancestors, node):
    name = ".".join(n.sval for n in node.funcname)
    if name == "format":
        fmt = first_arg(node)
        if has_percent_s(fmt):  # %s, не %L/%I
            yield Finding(
                rule_id="R013-plpgsql-format-without-using",
                vuln_class="PLPGSQL_UNSAFE",
                severity="high", risk_score=7,
                message="format() с %s — эквивалент конкатенации",
            )
```

### Phase 1.5 — `plpgsql_check` (ADR-0010)

В sandbox-БД с установленным расширением `plpgsql_check`:
```sql
SELECT * FROM plpgsql_check_function('find_user(text)', fatal_errors := false);
```

`plpgsql_check` сам сообщает о ряде проблем (mismatched types, недостижимый код, SQL-injection-кандидаты внутри `EXECUTE`). Findings подмешиваются в общий list.

### Phase 2 — LLM-судья

RAG: PG-docs PL/pgSQL `EXECUTE` + `format()`, CWE-89, EPAM PL/SQL→PL/pgSQL miграционный paper (`research/materials/05-peripheral.md` § 6 у нас уже описан в research).

LLM:
1. Проверяет, действительно ли передаваемая в `EXECUTE` строка содержит пользовательский ввод (часто параметр — это литерал из самой схемы; тогда low/info).
2. Если функция объявлена `SECURITY DEFINER` — повышает risk_score на 1.
3. Выписывает рекомендацию с конкретным синтаксисом `USING $1, $2`.

## Метрика покрытия

В eval-set: **10 примеров с `vuln_class == PLPGSQL_UNSAFE`** (5 `||`-конкатенаций + 5 `format() %s` + парные «good»-версии для проверки FP).

- Recall@iter1 ≥ 0.85.
- Precision ≥ 0.90 (есть редкие легитимные `format()` где `%s` оправдан — например, числовые литералы из enum'а).
- Δ risk_score: gold-fix через `USING` → 0.

## Связи

- **ADR-0004** — правила `R012`, `R013`.
- **ADR-0010** — PL/pgSQL бонусный путь, интеграция с `plpgsql_check`.
- **ADR-0005** — RAG: `kb.postgres` (`pg-docs-plpgsql-execute`).
- **research/materials/05-peripheral.md** — EPAM Code Migration, SQLGenie (executor как оракул).
- **research/materials/07-deterministic-tools/** — после reorg тут будут связанные тулзы.
- **PG docs** → https://www.postgresql.org/docs/current/plpgsql-statements.html#PLPGSQL-STATEMENTS-EXECUTING-DYN
- **`plpgsql_check`** → https://github.com/okbob/plpgsql_check

## Известные слабости детектора

1. **`plpgsql_check` сам признаёт ограниченное покрытие SQLi** — это сигнал, что нельзя полагаться только на него; pglast-правила обязательны.
2. **`EXECUTE` через bound variable**: `query := 'SELECT ...'; EXECUTE query USING ...;` — Phase 1 не видит, что `query` склеивалась раньше. Phase 2 (LLM) должен догадаться по контексту тела функции.
3. **Триггеры**: триггер-функции часто `SECURITY DEFINER`, в них `EXECUTE` тоже бывает — наша система их обрабатывает тем же путём.
4. **`PERFORM` с побочным эффектом** — отдельный класс «опасные побочные эффекты», `R017` в ADR-0010.
