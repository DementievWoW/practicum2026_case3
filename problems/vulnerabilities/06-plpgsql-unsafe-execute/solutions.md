# Варианты решения: PL/pgSQL небезопасный EXECUTE

## Альтернативные подходы к детекции

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Регекс `EXECUTE\s+.*\|\|` | 20 секунд | Промахи на многострочных, FP в комментариях | ❌ |
| B | `sqlglot` AST | Чисто Python | **`sqlglot` НЕ поддерживает PL/pgSQL** — критичный disqualifier | ❌ |
| C | `pglast.parse_plpgsql()` + Visitor по ExecuteStmt | Точное PG-native parsing | Парсер сложнее обычного SQL, требует внимания к dollar-quoting | ✅ ядро |
| D | C + анализ `format()` arguments на `%s` vs `%L`/`%I` | Покрывает второй типовой антипаттерн | Усложнение visitor | ✅ расширение |
| E | `plpgsql_check` в sandbox | **Внутренний анализатор PostgreSQL** — глубокая семантика | Сам авторы признают: «не для полного security-аудита»; ловит только часть SQLi | ✅ комплемент |
| F | LLM-only по тексту функции | Гибкий | FP/FN высокие; вне нашей политики (см. ADR-0004) | ❌ |
| G | Fine-tune модели на PL/SQL→PL/pgSQL миграциях | Лучший возможный recall | Дорого, EPAM показал ограниченный выигрыш (58-69%) | вне MVP |

## Эталонный fix

**Вариант 1 — параметризация через `USING`:**
```sql
RETURN QUERY EXECUTE 'SELECT * FROM users WHERE login = $1' USING login;
```

**Вариант 2 — `format()` с `%L`:**
```sql
RETURN QUERY EXECUTE format('SELECT * FROM users WHERE login = %L', login);
```

**Вариант 3 — комбо для динамического идентификатора:**
```sql
RETURN QUERY EXECUTE format('SELECT * FROM %I WHERE id = $1', tbl) USING key;
```

При наличии `SECURITY DEFINER` — обязательно добавить `SET search_path` (см. [05](../05-privilege-escalation-execute/)).

## Что выбрали и почему

**C + D + E (pglast + format-анализ + `plpgsql_check`)** — гибрид трёх инструментов с разной слепотой:

- **pglast** парсит PL/pgSQL точно, ловит `||`-конкатенацию.
- **format-анализатор** — отдельная проверка спецификаторов внутри `format()`. Без этой проверки `format('SELECT ... %s', login)` пройдёт как «выглядит как format → ок», что хуже чем явный `||`.
- **`plpgsql_check`** даёт семантический бонус (mismatched types, dead code, потенциально опасные `EXECUTE`). Признаёт собственную ограниченность по SQLi → не замена pglast-правил, а комплемент.

Это закрывает **бонусный критерий +10 баллов** (PL/pgSQL поддержка) и одновременно один из основных классов из baseline.

## Реализация

### Phase 1 — `R012` / `R013` (ADR-0004 + ADR-0010)

```python
class PlpgsqlExecuteConcat(Visitor):  # обходит parse_plpgsql AST
    def visit_ExecuteStmt(self, ancestors, node):
        if is_string_concat(node.query):  # A_Expr op '||' с переменной
            yield Finding(
                rule_id="R012-plpgsql-execute-concat",
                vuln_class="PLPGSQL_UNSAFE",
                severity="high", risk_score=8,
                evidence_refs=["CWE-89", "CAPEC-66"],
            )

class PlpgsqlFormatPercentS(Visitor):
    def visit_FuncCall(self, ancestors, node):
        if name_of(node) == "format" and has_percent_s(first_arg(node)):
            yield Finding(
                rule_id="R013-plpgsql-format-without-using",
                vuln_class="PLPGSQL_UNSAFE",
                severity="high", risk_score=7,
            )
```

### Phase 1.5 — `plpgsql_check` (ADR-0010)

В sandbox-БД (Docker-контейнер с расширением, см. ADR-0010 §C):
```sql
CREATE EXTENSION IF NOT EXISTS plpgsql_check;
-- временное создание функции с уникальным именем (BEGIN; ... ROLLBACK; обёртка)
SELECT * FROM plpgsql_check_function('audit_tmp_xxx()', fatal_errors := false);
```

Findings подмешиваются в общий list.

### Phase 2 — LLM-судья

RAG: PG-docs PL/pgSQL EXECUTE/format/USING; CWE-89; EPAM PL/SQL→PL/pgSQL paper.

Инструкция:
1. Подтвердить TP/FP (иногда `format('... %s', enum_literal)` оправдан с числовым enum).
2. Если функция `SECURITY DEFINER` — повысить `risk_score` на 1 (двойной удар).
3. Рекомендация с конкретным синтаксисом `USING $1, $2`.

## Метрика успеха

В eval-set: **10 примеров с `vuln_class == PLPGSQL_UNSAFE`**:
- 5 с `||`-конкатенацией.
- 5 с `format() %s`.
- 5 парных «good»-версий (для проверки FP).

| Метрика | Цель |
|---|---|
| Recall@iter1 | ≥ 0.85 |
| Precision | ≥ 0.90 |
| `plpgsql_check` интеграция работает | smoke test проходит |
| `overall_risk_score` после fix | 0 |

## Известные слабости и mitigations

| Слабость | Митигация |
|---|---|
| `plpgsql_check` признаёт ограниченное SQLi-покрытие | pglast-правила обязательны, не полагаемся только на `plpgsql_check` |
| `EXECUTE` через bound variable (`query := '...'; EXECUTE query;`) | Phase 1 пропустит; Phase 2 LLM должен догадаться по контексту тела |
| Триггер-функции часто `SECURITY DEFINER` + `EXECUTE` | Тот же путь, дополнительная проверка триггерных атрибутов |
| `PERFORM` с side-effect (UPDATE inside) | Отдельный класс «опасные побочные эффекты», `R017` в ADR-0010 |

## Связи с ADR

- **ADR-0004** — `R012`, `R013`.
- **ADR-0010** — PL/pgSQL бонусный путь, `plpgsql_check` интеграция.
- **ADR-0005** — `kb.postgres` (PL/pgSQL EXECUTE/format docs).
- **ADR-0007** — Sandbox с extension `plpgsql_check`.
