# Варианты решения: SQL Injection (классический)

## Альтернативные подходы к детекции

| # | Подход | Плюсы | Минусы | Решение для нас |
|---|---|---|---|---|
| A | **Только LLM-судья** (sql + промпт «найди SQLi») | Гибкий, видит «логические» инъекции | 100% evasion на adversarial-payloads ([IEEE 2025](../../../research/materials/04-security-attacks/p2sql-injection-langchain/)); галлюцинирует CWE-ID; inconsistent между прогонами | ❌ |
| B | **Только статика SAST** (semgrep/CodeQL по host-коду) | Детерминированно, аудируемо, быстро | Ловит f-strings и `.format()` в Python, но **не видит саму SQL-строку**, если она пришла извне; не работает на сгенерированном LLM SQL в рантайме | ⚠️ комплемент, не замена |
| C | **Только AST-парсинг SQL** (pglast по `sql_candidate`) | Парсит реальный AST PostgreSQL; быстро | Сам по себе SQL уже не содержит «склейки» — на этом этапе уже поздно: payload встроен | ⚠️ ловит только маркеры, не сам факт инъекции |
| D | **Гибрид: AST → findings → LLM-судья + RAG** | Покрывает оба слоя; LLM работает с уликами в промпте, а не «угадывает»; верифицируемые CWE-ID через RAG | Дороже в инженерии (11+ правил + RAG-коллекции) | ✅ **выбрали** |
| E | **Multi-judge consensus** (3 LLM голосуют) | Снижает inconsistency | × 3 латентность; для 40-сек бюджета не лезет | отложили |

## Эталонный fix (варианты, которые судья предлагает пользователю)

| Вариант | Когда применять | Пример |
|---|---|---|
| **Параметризация** | Литералы (значения) | `cursor.execute("SELECT ... WHERE login = %s", (login,))` |
| **Allow-list для идентификаторов** | `ORDER BY`, имена таблиц/колонок | `if order_by in {"id", "ts"}: ...` |
| **ORM-абстракция** | Когда возможно перейти на SQLAlchemy/Django ORM | автопараметризация |
| **Escape-функции** | ❌ DISCOURAGED по OWASP | `quote_literal`, `quote_ident` — только как last resort |

Судья **не должен** предлагать «экранирование вручную» — это antipattern из OWASP Cheat Sheet.

## Что выбрали и почему

**Гибрид (вариант D)** — единственный, дающий обе характеристики:
- **Низкий FN** на классических payloads (статика).
- **Низкий FP** на легитимных запросах (LLM-триаж).
- **Верифицируемые ссылки** на стандарты (RAG → `evidence.cwe_id`).

Подкреплено материалами:
- **IEEE 2025 «SQLi in LLM-Generated Queries»**: 100% evasion одиночных SAST → нужен LLM-слой поверх.
- **Trend Micro «LLM as a Judge»**: LLM судья работает только когда улика в промпте → даём ему findings.
- **OWASP SQLi Cheat Sheet**: единственно надёжная защита — параметризация → как baseline-рекомендация.

## Реализация

### Phase 1 — `R011-injection-marker` (ADR-0004)

`pglast.Visitor` + дополнительные эвристики:

```python
class InjectionMarker(Visitor):
    def visit_A_Expr(self, ancestors, node):
        # склейка строк в WHERE/ORDER BY с переменной
        if node.kind == AEXPR_OP and node.name[0].sval == "||":
            if has_user_input_marker(node):
                yield Finding(rule_id="R011-injection-marker",
                              vuln_class="SQL_INJ_CLASSIC",
                              severity="high", risk_score=10,
                              evidence_refs=["CWE-89", "CAPEC-66"])
```

Дополнительные регулярки в pre-AST стадии:
- `'\s*\|\|` (склейка кавычка + `||`),
- `format(...)` без `USING`,
- `$1::text \|\|`,
- литерал в `WHERE`, совпадающий с фрагментом `task_description`.

### Phase 1.5 — `semgrep` вне рантайма

`semgrep p/sql-injection` + `p/python.flask` / `p/python.django` в CI. Ловит f-strings, `%`, `.format()`, `+` в `cursor.execute(...)`. **Не часть рантайм-цикла**, упоминается на защите как «security by design».

### Phase 2 — LLM-судья + RAG (ADR-0004, ADR-0005)

LLM получает: SQL + findings от `R011` + top-5 чанков из `kb.cwe` (CWE-89), `kb.capec` (CAPEC-66), `kb.owasp` (Prevention Cheat Sheet).

Инструкция:
1. Подтвердить, что это действительно SQLi (отсеять FP: `'O\'Reilly'` — легитимный литерал).
2. Если TP — `risk_score=10`, `evidence={"cwe_id":"CWE-89", "capec_id":"CAPEC-66"}`.
3. Рекомендация — параметризация или allow-list с готовым примером.

### Антигаллюцинационный валидатор

Регексом извлекаем `CWE-\d+` / `CAPEC-\d+` из ответа judge. Если ID нет в `kb.cwe` / `kb.capec` — заменяем `evidence` на пустое + `metadata.unverified=true`.

## Метрика успеха

В eval-set (ADR-0006): **15 примеров с `vuln_class == SQL_INJ_CLASSIC`** (адаптации из PortSwigger PG + sqlmap).

| Метрика | Цель |
|---|---|
| Recall@iter1 | ≥ 0.80 |
| Precision (нет FP на параметризованных SELECT) | ≥ 0.90 |
| `overall_risk_score` после fix | < 4.0 |
| Доля findings с `unverified=false` | ≥ 0.95 |

## Известные слабости и mitigations

| Слабость | Митигация |
|---|---|
| Obfuscated payloads (casing, comments, encoding) — `R011` промахивается | Phase 2 + adversarial-тесты на `kb.payloads` |
| Stored injections (2nd-order) — payload в БД, выполняется потом | Документируем как known limitation; на одном SQL не поймать |
| Encoding attacks ([CVE-2025-1094](../../../research/materials/06-postgres-cves/cve-2025-1094-libpq-escaping/)) — BIG5/EUC_TW обход libpq escape | На уровне SQL уже поздно; фиксится обновлением libpq |
| LLM может галлюцинировать CWE-ID | Антигаллюцинационный валидатор по `kb.cwe` |

## Связи с ADR

- **ADR-0004** — гибридный аудитор, правило `R011`.
- **ADR-0005** — RAG `kb.cwe`, `kb.capec`, `kb.owasp`.
- **ADR-0007** — методология измерения Recall.
