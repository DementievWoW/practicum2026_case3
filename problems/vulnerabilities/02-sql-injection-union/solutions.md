# Варианты решения: Union-based Injection

## Альтернативные подходы к детекции

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Регекс по строке SQL (`UNION\s+SELECT`) | Тривиально | Огромный FP на легитимных analytical-`UNION` (отчёты по нескольким таблицам) | ❌ |
| B | AST-анализ `SelectStmt.op == SETOP_UNION` + проверка targets | Точно опознаёт структуру, отличает от `OR`/комментариев в строке | Не различает legitimate vs malicious — нужна семантика | ⚠️ часть решения |
| C | AST + эвристики на «probe-паттерны» (NULL,NULL; рассинхрон colcount; доступ к `information_schema`/`pg_catalog`) | Опознаёт типовые этапы атаки | Не покрывает кастомные payloads | ⚠️ Phase 1 base |
| D | **AST + эвристики + LLM-триаж с RAG (CAPEC-66 Union variant)** | Отсеивает analytical-`UNION` как FP, ловит хитрые payloads | Дороже | ✅ **выбрали** |
| E | Обучить классификатор (CodeBERT) | Может обучаться на корпусе SQLQueryShield | Не интерпретируем; нужен дополнительный pipeline | отложили (если время) |

## Эталонный fix (что предлагает судья)

Тот же, что и в [01-sql-injection-classic](../01-sql-injection-classic/):
1. **Параметризация** для значений.
2. **Allow-list** для идентификаторов.

Дополнительно — **отзыв `SELECT` на чувствительные таблицы у роли приложения** (принцип наименьших привилегий, OWASP ASVS V8):
```sql
REVOKE SELECT ON auth.users FROM app_role;
REVOKE SELECT ON pg_catalog.pg_authid FROM PUBLIC;  -- уже по дефолту
```

## Что выбрали и почему

**Гибрид C+D (AST-эвристики → LLM-триаж).** Чисто-AST правило (B) ловит структуру, но не семантику; legitimate `UNION ALL` в datawarehouse-стиле — частая практика, флагать его как high risk = неприемлимый FP-rate.

Эвристики «probe-паттернов» (`NULL,NULL,...`, рассинхрон столбцов, доступ к системным каталогам) — типовая последовательность атаки, она хорошо детектируется AST-обходом. LLM-триаж затем отсеивает legitimate сценарии: например, `SELECT id FROM orders UNION SELECT id FROM orders_archive` — явно отчёт, low risk.

## Реализация

### Phase 1 — `R005-union-suspicious` (ADR-0004)

```python
class UnionSuspicious(Visitor):
    def visit_SelectStmt(self, ancestors, node):
        if node.op != enums.SetOperation.SETOP_UNION:
            return
        # Эвристика 1: рассинхрон числа колонок
        upper = count_targets(node.larg)
        lower = count_targets(node.rarg)
        if upper != lower:
            yield Finding("R005-union-suspicious", risk_score=7,
                          note="число колонок не совпадает (probe?)")
        # Эвристика 2: probe-payload SELECT NULL, NULL, ...
        if has_null_only_select(node.rarg):
            yield Finding("R005-union-suspicious", risk_score=8)
        # Эвристика 3: доступ к системным каталогам в нижней части
        if references_information_schema_or_pg_catalog(node.rarg):
            yield Finding("R005-union-suspicious", risk_score=9,
                          evidence_refs=["CWE-89", "CAPEC-66"])
        # Эвристика 4: отзеркаливание литерала из верхнего WHERE в нижний SELECT
        if mirrors_where_literal(node):
            yield Finding("R005-union-suspicious", risk_score=8)
```

### Phase 2 — LLM-судья + RAG

Контекст: CAPEC-66 (Union variant), PortSwigger «Retrieving data from other tables», `kb.payloads` Union-section (для distillation, не для рекомендаций).

Промпт инструктирует **различать**:
- Легитимный analytical-`UNION` (`SELECT ... FROM live UNION SELECT ... FROM archive`) → FP, понизить severity до info.
- `UNION` с probe-паттернами или системными каталогами → TP, оставить risk_score 7-9.

## Метрика успеха

В eval-set: **10 примеров с `vuln_class == SQL_INJ_UNION`** (адаптации `sqlmap union_query.xml`) + 5 «good» примеров с legitimate analytical-`UNION` для FP-проверки.

| Метрика | Цель |
|---|---|
| Recall@iter1 | ≥ 0.80 |
| Precision (FP на analytical-`UNION`) | ≥ 0.85 |
| `overall_risk_score` после fix | < 4.0 |

## Известные слабости и mitigations

| Слабость | Митигация |
|---|---|
| Обфускация комментариями `UNION/*comment*/SELECT` | pglast AST устойчив к whitespace/comments — нормализует на парсе |
| Двухступенчатые атаки (UNION собирается через несколько API-вызовов) | Невозможно поймать на одном SQL; известное ограничение |
| Legitimate analytical-`UNION` | LLM-триаж Phase 2 + явная инструкция в промпте |
| `INTERSECT` / `EXCEPT` варианты | Расширение правила `R005b` при необходимости |

## Связи с ADR

- **ADR-0004** — правило `R005-union-suspicious`.
- **ADR-0005** — RAG `kb.capec` (CAPEC-66), `kb.owasp`.
- **ADR-0007** — методология Recall/Precision.
