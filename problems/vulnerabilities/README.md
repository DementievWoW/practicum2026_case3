# Уязвимости SQL — 9 классов под микроскопом

Источник классификации — `baseline1.SecurityAuditor.VULN_CLASSES` (`baseline1.py:80-90`).
Шкала риска — 0–10 (определена в `baseline1.Vulnerability.risk_score`).
Порог одобрения — `RISK_THRESHOLD = 4.0` (`baseline1.py:91`).

## Карта

| # | `vuln_class` | Риск | CWE | CAPEC | Phase 1 правило (ADR-0004) | Mandatory |
|---|---|---|---|---|---|---|
| 01 | `SQL_INJ_CLASSIC` | 10 | CWE-89 | CAPEC-66 | `R011-injection-marker` | ⭐ |
| 02 | `SQL_INJ_UNION` | 9 | CWE-89 | CAPEC-66 (вариант) | `R005-union-suspicious` | ⭐ |
| 03 | `SQL_INJ_TIME` | 8 | CWE-89 | CAPEC-7 | `R006-pg-sleep` |  |
| 04 | `DML_NO_WHERE` | 9 | CWE-1284 | — | `R002`/`R003-update-delete-no-where` | ⭐ |
| 05 | `PRIV_ESCALATE` | 8 | CWE-269 | CAPEC-470 | `R007-security-definer-no-search-path` |  |
| 06 | `PLPGSQL_UNSAFE` | 9 | CWE-89 (variant) | CAPEC-66 | `R008-plpgsql-execute-concat` | бонус |
| 07 | `DIRECT_SENSITIVE` | 6 | CWE-200, CWE-359 | — | `R009-sensitive-columns` | ⭐ |
| 08 | `SELECT_STAR` | 5 | CWE-1295 | — | `R001-select-star` | ⭐ |
| 09 | `NO_PAGINATION` | 4 | CWE-770 | — | `R004-no-limit` |  |

## Принципы детекции (общий шаблон)

Каждая уязвимость детектится в **двух фазах** (ADR-0004):

**Phase 1 — детерминированный AST через `pglast`:**
```python
class Rule(Visitor):
    def visit_<NodeType>(self, ancestors, node):
        if <условие>:
            yield Finding(
                rule_id="R0XX-<short>",
                vuln_class="<KEY_FROM_VULN_CLASSES>",
                severity="high|medium|low",
                risk_score=<0..10>,
                location=<line:col>,
                snippet=<piece of SQL>,
                message=<human-readable>,
                evidence_refs=[<CWE/CAPEC/OWASP>],
            )
```

**Phase 2 — LLM-судья поверх findings + RAG:**
- Подтянуть top-5 чанков из `kb.cwe` ∪ `kb.capec` ∪ `kb.owasp` по `vuln_class`.
- Запрос к LLM: «подтвердить / отклонить как FP, выставить risk_score, написать description и recommendation».
- Вернуть финальный `Vulnerability` по контракту `baseline1`.

## Метрика покрытия

Для каждого класса в eval-set (60 SQL × 2 NL = 120 пар, ADR-0006) считаем:
- **Recall@iter1** — доля примеров с `gt_vuln_class == X`, где судья поднял класс X на первой итерации.
- **Recall@iterAny** — то же, но на любой из 5 итераций (учитывает reflection-цикл).
- **Precision** — доля корректных детектов среди всех, где судья поднял X (важно — нет ли FP).
- **Δ risk_score** между iter 1 и финалом (динамика, требуется ТЗ).

## Mandatory-set для зачёта (5 классов)

Минимально достаточный набор, по убыванию вклада в баллы и сложности:
1. **SELECT \*** — детект тривиален, демонстрирует «работу» аудитора с порога.
2. **UPDATE/DELETE без WHERE** — высокий риск + простая детекция = надёжные баллы.
3. **DIRECT_SENSITIVE** — даёт PII-демку, попадает в live-demo.
4. **SQL_INJ_CLASSIC** — флагман, без него «security» не звучит.
5. **SQL_INJ_UNION** — расширение SQLi семейства, +1 класс почти даром.

Если останется время — `PLPGSQL_UNSAFE` (+10 бонус) и `SQL_INJ_TIME`.

## Ссылки

- Контракт: `baseline1.py` (`VULN_CLASSES`, `Vulnerability`, `AuditResult`)
- ADR-0004: гибридный аудитор (детерминированный + LLM)
- ADR-0005: RAG-база (CWE/CAPEC/OWASP)
- ADR-0010: PL/pgSQL бонусный путь
- materials/04-security-attacks, materials/05-security-benchmarks-datasets, materials/06-postgres-cves
