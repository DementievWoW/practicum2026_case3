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

## Внешние ссылки

- **CWE-269**, **CAPEC-470** — в шапке.
- **PG docs** — https://www.postgresql.org/docs/current/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY
- **research/materials/06-postgres-cves/cve-2025-8714-pg-dump-injection/** — практический пример эскалации через pg_dump meta.

## Варианты решения

См. [solutions.md](solutions.md).
