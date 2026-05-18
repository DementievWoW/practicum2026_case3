# Варианты решения: Прямой доступ к чувствительным полям

## Альтернативные подходы к детекции

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Регекс по имени колонки в SQL-строке | Тривиально | Не различает `SELECT *` (требует expand), не работает на алиасах | ❌ |
| B | **AST `ColumnRef` + словарь регексов на чувствительные имена** | Точно, видит aliasing, видит обёртки маскирующих функций | Не покрывает не-английские имена | ✅ ядро |
| C | B + expand `SELECT *` через `information_schema.columns` из sandbox | Закрывает SELECT * | Требует sandbox-БД с актуальной схемой | ✅ расширение |
| D | B + детект ПДн в literals (Luhn, mod-101 СНИЛС, ИНН checksum) | Ловит PII, просочившийся в код | Доп. бюджет проверки; FP на тестовых данных | ⚠️ Phase 1bis |
| E | **Microsoft Presidio** NER на тексте запроса | 17+ entity types из коробки | Тяжёлый, overhead; больше для текстового контента, не для SQL | для текста, не SQL |
| F | Обучить классификатор на `securesql-benchmark` | Лучший возможный recall, доменно-точный | Дорого, нужно поддерживать | вне MVP |

## Эталонный fix (что предлагает судья)

| Сценарий | Fix |
|---|---|
| Данные нужны для UI | View с маскированием (`LEFT/SUBSTRING`, hash) |
| Нужен агрегат | Только агрегат, без сырых значений (`COUNT(*)` вместо `SELECT card_number, cvv`) |
| Полный доступ для конкретной задачи | Колоночные привилегии: `GRANT SELECT (id, login, email)`, `REVOKE` на чувствительные |
| Хранение | `pgp_sym_encrypt` для at-rest шифрования |
| Multi-tenant | RLS policy `WHERE tenant_id = current_setting(...)::int` |

## Что выбрали и почему

**B + C + D** как Phase 1; **LLM-судья в Phase 2 различает категории** (FP-фильтр).

Аргументы:
- B даёт быстрый и интерпретируемый детектор без зависимостей от ML.
- C закрывает кейс `SELECT *`, который чаще всего и есть путь утечки (раскрытие в `*` всех колонок включая чувствительные).
- D ловит PII в WHERE-литералах — типовая ошибка «логин в логи».
- **Presidio (E)** избыточен для SQL: их регексы под текст и обращения, мы их **переиспользуем для словаря B**, но не запускаем NER.

## Реализация

### Phase 1 — `R009-sensitive-columns` (ADR-0004)

```python
SENSITIVE_PATTERNS = [
    (r"(?i)^(password|passwd|pwd|secret|api[_-]?key|token|access[_-]?token)$", "critical", 8),
    (r"(?i)^(card[_-]?(number|num|no)|pan|cvv|cvc)$", "critical", 8),
    (r"(?i)^(ssn|social[_-]?security)$", "high", 7),
    (r"(?i)^(passport|inn|snils|ogrn)$", "high", 7),
    (r"(?i)^(email|phone|mobile|tel)$", "medium", 5),
    (r"(?i)^(dob|birth(_?date|day))$", "medium", 5),
]

class SensitiveColumns(Visitor):
    def visit_ColumnRef(self, ancestors, node):
        col_name = node.fields[-1].sval
        for pat, severity, score in SENSITIVE_PATTERNS:
            if re.match(pat, col_name):
                if is_inside_func(ancestors, names={
                    "coalesce", "mask", "digest", "hash",
                    "left", "substring", "pgp_sym_decrypt",
                }):
                    continue  # маскирующая обёртка → не finding
                yield Finding(
                    rule_id="R009-sensitive-columns",
                    vuln_class="DIRECT_SENSITIVE",
                    severity=severity, risk_score=score,
                    location=node.location,
                    evidence_refs=["CWE-200", "CWE-359"],
                )
```

### Phase 1b — `R009-expand-star`

Если в `targetList` есть `A_Star`, идём в `information_schema.columns` sandbox-БД, раскрываем `*` в список колонок. Если среди них чувствительные — выпускаем `R009` finding с указанием колонок (вдобавок к `R001-select-star`).

### Phase 1bis — `R009b-pii-in-literal`

Регулярки + checksum для literals в `WHERE`/`VALUES`:
- Карта (16 цифр) → Luhn.
- СНИЛС → mod-101.
- ИНН (10/12 цифр) → контрольная сумма.

Risk_score = 6-7.

### Phase 2 — LLM-судья

RAG: `kb.pii` (наши регексы + примеры с RU валидаторами), CWE-200/359, OWASP ASVS V8.

Инструкция:
1. FP-проверка: `password_reset_at` — не пароль, это timestamp.
2. Контекст: фильтр `WHERE user_id = current_user_id` → low (self-access).
3. Рекомендация — view с маскированием / колоночные привилегии / шифрование.

## Метрика успеха

В eval-set: **15 примеров с `vuln_class == DIRECT_SENSITIVE`**:
- 8 запросов к чувствительным колонкам без маскирования.
- 5 запросов к ним же с маскированием (FP-проверка).
- 2 запроса с PII в literals.

| Метрика | Цель |
|---|---|
| Recall@iter1 | ≥ 0.85 |
| Precision | ≥ 0.80 (FP на похожих именах вроде `system_notification_email`) |
| `overall_risk_score` после fix | < 4.0 |

## Известные слабости и mitigations

| Слабость | Митигация |
|---|---|
| Не-английские имена колонок (`номер_паспорта`) | Расширить словарь RU-корнями |
| Aliasing в view: `SELECT col_a FROM v_users` где view скрывает PII | Резолв через `information_schema.views` (вне MVP) |
| Boolean flags вроде `has_password BOOLEAN` ловятся regex | Phase 2 проверяет тип из sandbox-схемы |
| JOIN-leaks (запрос к view без PII, но JOIN к таблице с PII) | Known limitation (side-channel) |

## Связи с ADR

- **ADR-0004** — `R009`, `R009b`.
- **ADR-0005** — `kb.pii` коллекция RAG (Presidio regex + RU валидаторы).
- **ADR-0007** — sandbox с `information_schema` для `*`-expand.
