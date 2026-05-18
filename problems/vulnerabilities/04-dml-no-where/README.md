# 04 — UPDATE / DELETE без WHERE

- **`vuln_class`:** `DML_NO_WHERE`
- **Риск:** 9/10
- **CWE:** [CWE-1284 — Improper Validation of Specified Quantity in Input](https://cwe.mitre.org/data/definitions/1284.html) (косвенно), либо CWE-1289 / общий «Logic / Authorization Errors».
- **CAPEC:** прямой паттерна нет, концептуально близко к **CAPEC-66** (если попало через injection) или к классу «Destructive operation due to missing predicate».

## Что

Запрос `UPDATE table SET ...` или `DELETE FROM table` **без условия `WHERE`** (или с предикатом, который всегда истинный, типа `WHERE 1=1`). Применяется ко всем строкам таблицы. Часто результат опечатки или копипасты — в проде сразу инцидент.

## Почему опасно (риск 9)

Прямой data integrity disaster:
- **`UPDATE clients SET balance = 0`** — обнулить все балансы.
- **`DELETE FROM orders`** — потеря исторических данных.
- **`DELETE FROM audit_log`** — удаление улик, anti-forensics.

Восстановление возможно только из бэкапа. SLA нарушается, репутационный ущерб высокий. По шкале baseline = 9 (на ступень выше SELECT-уязвимостей, не нарушающих integrity).

В ТЗ (`tusk`) описание: «Модификация или удаление всех строк таблицы из-за отсутствия условия фильтрации».

## PostgreSQL specifics

Postgres даёт несколько «защитных» механизмов, которыми **никто не пользуется по умолчанию**:

- **`set statement_timeout`** — не спасает, если запрос быстрый (`DELETE` без `WHERE` использует sequential scan, но всё равно может уложиться в timeout).
- **`SET default_transaction_read_only = on`** для роли — снимает право DML вообще. Применимо для аналитических ролей.
- **Триггеры** `BEFORE UPDATE/DELETE FOR EACH STATEMENT WHEN (NEW.id IS NULL)` — самопальная защита, неуклюжая.
- **Row-Level Security (RLS)** — мощная, но требует явной policy на каждую таблицу.
- **`pg_safeupdate`** (расширение) — отказывает `UPDATE`/`DELETE` без `WHERE`. Не дефолтное.

**Семантические ловушки:**
- `DELETE FROM t USING t2 WHERE ...` — есть `WHERE`, но если `t2` пуст или join cartesian, эффект может быть таким же.
- `UPDATE t SET x = y FROM t2` без `WHERE` — то же.
- `DELETE FROM t WHERE id IN (SELECT id FROM t2)` где `t2` пуст → нулевое удаление. Не наша проблема, но похоже.
- `WHERE 1=1` / `WHERE true` — синтаксически WHERE есть, семантически нет.

## Пример антипаттерна

**Тривиальный:**
```sql
DELETE FROM orders;
UPDATE clients SET balance = 0;
```

**С маскировкой:**
```sql
UPDATE clients SET balance = 0 WHERE 1 = 1;
DELETE FROM orders WHERE TRUE;
DELETE FROM orders WHERE created_at < now();  -- всегда истинно, фактически удаляет всё
```

**JOIN cartesian:**
```sql
-- Намерение: «удалить orders клиентов из чёрного списка»
DELETE FROM orders USING blacklist;  -- забыли ON-условие, удалит всё
```

## Эталонный fix

Всегда явный `WHERE` с predicate, ссылающимся на **identifying column** (обычно PK):
```sql
DELETE FROM orders WHERE id = $1;
UPDATE clients SET balance = $1 WHERE client_id = $2;
```

Для массового удаления — **soft-delete pattern**:
```sql
UPDATE orders SET deleted_at = now() WHERE created_at < now() - interval '1 year';
```

Дополнительные защиты:
```sql
-- Транзакция с проверкой количества затронутых строк
BEGIN;
DELETE FROM orders WHERE ...;
-- если затронуто слишком много — ROLLBACK
ROLLBACK;
```

И на уровне роли:
```sql
REVOKE DELETE ON orders FROM analytics_role;
GRANT DELETE ON orders TO admin_role;  -- только админ
```

## Как мы детектим

### Phase 1 — `R002-update-no-where` / `R003-delete-no-where` (ADR-0004)

```python
class UpdateNoWhere(Visitor):
    def visit_UpdateStmt(self, ancestors, node):
        if node.whereClause is None:
            yield Finding(
                rule_id="R002-update-no-where",
                vuln_class="DML_NO_WHERE",
                severity="high", risk_score=9,
                message="UPDATE без WHERE — затрагивает все строки таблицы",
                evidence_refs=["CWE-1284"],
            )
        elif is_always_true(node.whereClause):
            yield Finding(rule_id="R002-update-no-where", ..., extra="WHERE всегда истинно")

class DeleteNoWhere(Visitor):
    def visit_DeleteStmt(self, ancestors, node):
        if node.whereClause is None:
            yield Finding("R003-delete-no-where", risk_score=9, ...)
```

Где `is_always_true` опознаёт:
- `A_Const(boolval=True)` → `WHERE true`.
- `A_Expr` вида `A_Const = A_Const` где значения совпадают → `WHERE 1=1`.
- Тождественные сравнения (`x = x`) — опционально, нечасто.

**Edge cases:**
- `DELETE FROM t USING ...` с пустым WHERE — то же правило, JOIN без условия flag'ить отдельно (`R005`-related или новое правило).
- `WITH cte AS (...) DELETE FROM t USING cte` — `whereClause` = None, но семантически фильтр в `USING`. **Документировать как known limitation**, либо отдельное правило проверяет, что в `USING`-части есть join condition.

### Phase 2 — LLM-судья

RAG: CWE-1284, OWASP Cheat Sheet (Least Privilege), PG docs (`pg_safeupdate`).

LLM проверяет:
1. Действительно ли отсутствие `WHERE` намеренное? (Например, при **TRUNCATE-like usecase** в миграциях — TP с low risk).
2. Если намеренное массовое удаление — рекомендация: использовать `TRUNCATE` (быстрее) или soft-delete.
3. Иначе — высокий риск, рекомендация добавить predicate по PK.

## Метрика покрытия

В eval-set: **10 примеров с `vuln_class == DML_NO_WHERE`** (5 `UPDATE` + 5 `DELETE`, разные таблицы из `data_model_sql/`).

- Recall@iter1 ≥ 0.95 (правило тривиальное).
- Precision ≥ 0.95 (легитимных «массовых DML без WHERE» в продукционном коде почти нет).
- Δ risk_score: gold-fix добавляет `WHERE id = $1` → 0.

## Связи

- **ADR-0004** — правила `R002`, `R003`.
- **ADR-0005** — RAG-чанки про default privileges, RLS, `pg_safeupdate`.
- **PostgreSQL** — `pg_safeupdate` extension, `default_transaction_read_only`.
- **OWASP ASVS** V8 — Least Privilege.

## Известные слабости детектора

1. **`USING` без join condition** — Phase 1 пропускает; план: вторая стадия проверяет `JoinExpr.quals is None`.
2. **CTE-обёртки** — `WITH t AS (DELETE ...) SELECT count(*) FROM t` — pglast парсит корректно, наше правило применимо.
3. **Условие через переменную PL/pgSQL**: `DELETE FROM t WHERE x = my_var` — если `my_var = NULL`, удалит 0 строк (NULL-сравнения), не наша проблема, но похожий silent-failure.
4. **`TRUNCATE`** — наша система не должна его одобрять без явного намерения, но это не `DML_NO_WHERE`, а отдельный класс (можно расширить ADR-0004).
