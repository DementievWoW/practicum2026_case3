# Варианты решения: UPDATE / DELETE без WHERE

## Альтернативные подходы к детекции

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Регекс `(UPDATE\|DELETE).*\b(?!WHERE)` | 30 секунд | Ломается на многострочных, на `WHERE 1=1`, на `USING` | ❌ |
| B | `sqlfluff` правило ST/CV | Готовое | Из коробки правило отсутствует — надо писать кастом | ❌ |
| C | **AST: `UpdateStmt.whereClause is None` / `DeleteStmt.whereClause is None`** | Тривиально точно; покрывает многострочные | Не покрывает `WHERE 1=1` без доп. логики | ✅ ядро |
| D | C + детектор always-true (`A_Const(boolval=True)`, `1=1`, `x=x`) | Покрывает маскировку | Нужна доп. логика | ✅ расширение |
| E | EXPLAIN + предсказание affected rows > N | Видит cartesian через `USING` без join | Не работает без sandbox-данных | ⚠️ опциональный комплемент |
| F | `pg_safeupdate` extension в БД | Жёстко блокирует на уровне БД | Не контроль аудитора, а runtime guard | для прод-deploy |
| G | `Valk Guard` (см. research/materials/07-deterministic-tools/valk-guard/) | Готовый линтер с этим правилом | Внешняя зависимость; написана под другие use-case'ы | референс для self-check |

## Эталонный fix (что предлагает судья)

| Сценарий | Fix |
|---|---|
| DML по одной строке | `... WHERE id = $1` |
| Массовое логическое удаление | `UPDATE ... SET deleted_at = now() WHERE created_at < ...` (soft-delete) |
| Намеренная очистка таблицы | `TRUNCATE TABLE t` (быстрее, явное намерение) — отдельная команда |
| Аналитическая роль | На уровне БД `ALTER ROLE analytics SET default_transaction_read_only = on` |

Судья **не должен** одобрять `WHERE TRUE`/`WHERE 1=1` как fix — это та же проблема.

## Что выбрали и почему

**C + D (AST + always-true детектор)** как Phase 1, **F как рекомендация** на уровне БД.

Аргументы:
- AST-проверка тривиальна, near-100% Recall, минимум FP.
- Always-true детектор закрывает маскировку — реальный паттерн в incident reports.
- `pg_safeupdate` рекомендуем заказчику как defence-in-depth, но не как замену аудитору (это runtime, не review-time).
- EXPLAIN-проверка affected-rows — overkill для MVP; добавляем как side-warning, не как primary правило.

## Реализация

### Phase 1 — `R002` / `R003` (ADR-0004)

```python
class UpdateNoWhere(Visitor):
    def visit_UpdateStmt(self, ancestors, node):
        if node.whereClause is None:
            yield Finding(
                rule_id="R002-update-no-where",
                vuln_class="DML_NO_WHERE",
                severity="high", risk_score=9,
                evidence_refs=["CWE-1284"],
            )
        elif is_always_true(node.whereClause):
            yield Finding(rule_id="R002-update-no-where", risk_score=9,
                          note="WHERE всегда истинно (маскировка)")

class DeleteNoWhere(Visitor):
    def visit_DeleteStmt(self, ancestors, node):
        if node.whereClause is None:
            yield Finding("R003-delete-no-where", risk_score=9)
```

`is_always_true` распознаёт:
- `A_Const(boolval=True)` → `WHERE true`.
- `A_Expr` вида `A_Const = A_Const` с равными значениями → `WHERE 1=1`.
- Тождества `x = x` (опционально).

**Edge case** — `DELETE FROM t USING ...` с пустым WHERE: правило срабатывает, но дополнительно проверяем, есть ли join-condition в `USING`-части. Если нет — отдельный finding «cartesian DELETE».

### Phase 2 — LLM-судья

RAG: CWE-1284, OWASP Cheat Sheet (Least Privilege), PG docs (`pg_safeupdate`).

LLM:
1. Намеренное массовое удаление? (миграция, очистка кеша) → рекомендация `TRUNCATE` + low severity.
2. Иначе — high severity, рекомендация predicate по PK.
3. Обязательно вторая стадия рекомендации — `default_transaction_read_only` или `pg_safeupdate` на уровне БД.

## Метрика успеха

В eval-set: **10 примеров с `vuln_class == DML_NO_WHERE`** (5 `UPDATE` + 5 `DELETE`).

| Метрика | Цель |
|---|---|
| Recall@iter1 | ≥ 0.95 |
| Precision | ≥ 0.95 (legitimate-DML без WHERE в продукционном коде почти нет) |
| `overall_risk_score` после fix | 0 |

## Известные слабости и mitigations

| Слабость | Митигация |
|---|---|
| `USING` без join-condition (cartesian) | Доп. правило поверх `R003` (отдельный finding) |
| CTE-обёртка: `WITH t AS (DELETE ...) SELECT ...` | pglast парсит, правило работает на внутреннем DeleteStmt |
| Условие через NULL-переменную в PL/pgSQL: `DELETE FROM t WHERE x = my_var` где `my_var IS NULL` | Silent zero-effect, не наш класс, документируем |
| `TRUNCATE` без явного намерения | Отдельный класс, можно расширить ADR-0004 |

## Связи с ADR

- **ADR-0004** — правила `R002`, `R003`.
- **ADR-0005** — `kb.postgres` (`pg_safeupdate`, `default_transaction_read_only`).
- **ADR-0007** — методология; EXPLAIN-affected-rows как опциональный side-check.
