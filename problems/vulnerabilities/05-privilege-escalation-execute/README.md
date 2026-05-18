# 05 — Privilege Escalation через EXECUTE / SECURITY DEFINER

- **`vuln_class`:** `PRIV_ESCALATE`
- **Риск:** 8/10
- **CWE:** [CWE-269 — Improper Privilege Management](https://cwe.mitre.org/data/definitions/269.html), также [CWE-94 — Code Injection](https://cwe.mitre.org/data/definitions/94.html).
- **CAPEC:** [CAPEC-470 — Expanding Control over OS from Database](https://capec.mitre.org/data/definitions/470.html).

## Что

Функция в PostgreSQL объявлена с атрибутом `SECURITY DEFINER` (выполняется с правами **владельца функции**, а не вызывающего) **без явной фиксации `search_path`**. Атакующий, у которого есть `CREATE` в любой схеме, расположенной выше в `search_path` (например, `pg_temp`), может создать там объект с тем же именем, что использует функция → её следующий вызов выполнит код атакующего с правами владельца.

Каноническое предупреждение: [PostgreSQL docs § Writing SECURITY DEFINER Functions Safely](https://www.postgresql.org/docs/current/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY).

## Почему опасно (риск 8)

- Если владелец функции — `postgres` (superuser), компрометация = полный контроль БД.
- Если владелец — обычный application-owner, всё равно эскалация **из роли пользователя → в роль application_owner**, у которой обычно `SELECT`/`UPDATE` на чувствительные таблицы.
- Атака **тихая**: следов в логах нет (всё происходит внутри функции, которую дёрнул легитимный код).

Риск 8 (а не 10), потому что:
- Эксплуатация требует, чтобы у атакующего был **`CREATE` в какой-то схеме**, проходящей по `search_path` (обычно `pg_temp` или public).
- Многие развертывания не имеют пользовательских `SECURITY DEFINER` функций вообще.

## PostgreSQL specifics

**Анатомия атаки** (классическая):
1. Владелец БД создаёт функцию:
   ```sql
   CREATE FUNCTION admin_lookup(login text) RETURNS bigint
     LANGUAGE plpgsql SECURITY DEFINER AS $$
     DECLARE r bigint;
     BEGIN
       SELECT id INTO r FROM users WHERE username = login;
       RETURN r;
     END $$;
   ```
   **Дефект:** нет `SET search_path`.
2. Атакующий, имея обычную роль, создаёт в `pg_temp` свою функцию или таблицу с именем `users`:
   ```sql
   CREATE TEMP TABLE users (id bigint, username text);
   INSERT INTO users VALUES (999, 'admin');
   ```
3. Атакующий зовёт `SELECT admin_lookup('admin')`. Внутри функции `search_path` начинается с `pg_temp` → берётся **temp-users**, а не реальный.
4. Через подмену типов / `RAISE NOTICE` / SECURITY DEFINER-вызов другой функции атакующий может выполнить произвольный SQL в контексте владельца.

**Защитные практики (из PG docs):**
```sql
CREATE FUNCTION admin_lookup(login text) RETURNS bigint
  LANGUAGE plpgsql SECURITY DEFINER
  SET search_path = pg_catalog, pg_temp  -- ВАЖНО: явно фиксируем
  AS $$ ... $$;

REVOKE ALL ON FUNCTION admin_lookup(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION admin_lookup(text) TO app_role;
```

Ещё надёжнее — **квалифицированные имена** внутри функции (`public.users` вместо `users`), плюс `SET search_path`.

## Пример антипаттерна

```sql
-- УЯЗВИМО: SECURITY DEFINER без SET search_path
CREATE OR REPLACE FUNCTION public.get_user_balance(uid bigint)
RETURNS numeric
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE bal numeric;
BEGIN
    SELECT balance INTO bal FROM accounts WHERE user_id = uid;
    RETURN bal;
END;
$$;
```

И часто рядом — отсутствие `REVOKE FROM PUBLIC`, то есть вызвать может **кто угодно**.

## Эталонный fix

```sql
CREATE OR REPLACE FUNCTION public.get_user_balance(uid bigint)
RETURNS numeric
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp  -- ← обязательно
AS $$
DECLARE bal numeric;
BEGIN
    SELECT balance INTO bal FROM public.accounts WHERE user_id = uid;  -- квалифицированное имя
    RETURN bal;
END;
$$;

REVOKE ALL ON FUNCTION public.get_user_balance(bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_user_balance(bigint) TO app_role;
```

Три обязательных слоя:
1. `SET search_path = ...` (фиксация схемы).
2. Квалифицированные имена в теле функции.
3. `REVOKE FROM PUBLIC` + `GRANT EXECUTE TO <конкретная роль>`.

## Как мы детектим

### Phase 1 — `R007-security-definer-no-search-path` (ADR-0004)

`pglast.Visitor` обходит `CreateFunctionStmt`:

```python
def visit_CreateFunctionStmt(self, ancestors, node):
    options = {opt.defname: opt for opt in (node.options or [])}
    is_definer = (
        "security" in options
        and options["security"].arg.boolval  # security definer = TRUE
    )
    if not is_definer:
        return
    has_search_path = any(
        opt.defname == "set"
        and opt.arg.name == "search_path"
        for opt in (node.options or [])
    )
    if not has_search_path:
        yield Finding(
            rule_id="R007-security-definer-no-search-path",
            vuln_class="PRIV_ESCALATE",
            severity="high", risk_score=8,
            message="SECURITY DEFINER без SET search_path — privilege escalation через pg_temp/search_path hijack",
            evidence_refs=["CWE-269", "CAPEC-470", "PG-docs#sql-createfunction"],
        )
```

Дополнительные эвристики:
- Тело функции содержит **неквалифицированные имена** объектов (`SELECT ... FROM users` вместо `FROM public.users`) → warning (часто сопровождает основную уязвимость).
- Отсутствие `REVOKE FROM PUBLIC` в той же миграции → info-level finding.

### Phase 2 — LLM-судья

RAG: PG-docs «Writing SECURITY DEFINER Functions Safely», CAPEC-470, CWE-269.

LLM подтверждает:
1. Действительно ли это уязвимость (иногда `SECURITY DEFINER` обоснован, например, обёртка для контролируемого доступа). В таком случае проверяет наличие компенсирующих защит.
2. Формирует рекомендацию с конкретным синтаксисом `SET search_path = pg_catalog, pg_temp` и `REVOKE FROM PUBLIC`.

## Метрика покрытия

В eval-set: **10 примеров с `vuln_class == PRIV_ESCALATE`** (адаптации примеров из PG docs про небезопасные `SECURITY DEFINER` функции).

- Recall@iter1 ≥ 0.85.
- Precision ≥ 0.90 (есть редкие легитимные случаи — обоснованные обёртки для контролируемого admin-доступа).
- Δ risk_score: gold-fix с `SET search_path` + `REVOKE` → 0.

## Связи

- **ADR-0004** — правило `R007`.
- **ADR-0005** — RAG-коллекция `kb.postgres` (SECURITY DEFINER section).
- **ADR-0010** — PL/pgSQL бонусный путь (этот класс — на стыке).
- **research/materials/06-postgres-cves/cve-2025-8714-pg-dump-injection/** — практический пример эскалации через pg_dump meta.
- **PG docs** → https://www.postgresql.org/docs/current/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY

## Известные слабости детектора

1. **Динамический `search_path`** — функция выставляет `search_path` через `EXECUTE 'SET search_path = ' || param` — Phase 1 не видит. Поднимаем в Phase 2.
2. **Цепочки SECURITY DEFINER** — функция A (`SECURITY DEFINER`, безопасная) зовёт функцию B (`SECURITY DEFINER`, опасная). Phase 1 проверяет каждую отдельно, но цепочечный анализ — отдельная задача (вне MVP).
3. **`SECURITY INVOKER` (дефолт)** не флагается — это ожидаемо. Если разработчик забыл указать `DEFINER`, наш аудитор спокойно одобрит — это правильное поведение.
