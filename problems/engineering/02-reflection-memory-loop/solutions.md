# Варианты решения: Reflection-память между итерациями

## Альтернативные подходы

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | Подать `AuditResult` дословно в промпт generator'а | Минимум инженерии | Длинно, перегружает контекст; generator не выделяет «урок» | ⚠️ baseline |
| B | **Отдельный reflector-узел: переводит findings → структурированный `Lesson`** | Reflexion-паттерн; чистая абстракция; легко логировать | Доп. узел, +1 LLM-вызов на retry | ✅ выбрали |
| C | Self-Refine: одна LLM сама критикует и правит | Самый простой граф | Не покрывает hybrid (детерминированные findings из Phase 1) | ❌ не подходит |
| D | Reflexion-style полный verbal RL (память о всех попытках навсегда) | Накапливает знания между сессиями | Слишком сложно; не нужно за хакатон | вне MVP |
| E | RetrySQL: дообучить модель на retry-парах | SOTA подход | Дорого, нужны данные; вне MVP | для v2 |
| F | R³ Review-Rebuttal-Revision (трёхфазный консенсус) | Альтернативная архитектура | Перестройка графа; +2 LLM-вызова на итерацию | для v2 |

## Эталонный формат `Lesson`

```python
@dataclass
class Lesson:
    rule_id: str       # например, "DML_NO_WHERE"
    lesson: str        # 1-3 предложения «не повторяй вот так»
    example_bad: str   # фрагмент проблемного SQL из предыдущей итерации
    example_good: str  # как должно было быть
```

В системный промпт generator'а:
```
### Reflection memory (lessons from previous attempts)
- [DML_NO_WHERE] Любой UPDATE/DELETE по таблице clients требует predicate по PK.
  Плохо:  UPDATE clients SET balance = 0
  Хорошо: UPDATE clients SET balance = 0 WHERE client_id = $1

- [SELECT_STAR] В отчётах по PII-таблицам не используй SELECT *.
  Плохо:  SELECT * FROM clients
  Хорошо: SELECT id, full_name, email FROM clients
- ...
```

## Что выбрали и почему

**B — отдельный reflector-узел.** Аргументы:

- **Чистое разделение ролей**: generator пишет SQL, judge оценивает, reflector переписывает findings в инструкции. Это идеально ложится на LangGraph state-граф (ADR-0002).
- **Дешевизна reflector'а** — задача проще generator'а (видит готовые findings, не пишет SQL). Перевод на Qwen 7B (вместо 32B) экономит x4-5 (ADR-0008).
- **Логируемо**: в Langfuse-трассе видна цепочка `iter1.findings → iter1.lesson → iter2.generator.prompt`. Это и есть «прозрачный лог», требуемый ТЗ.
- **Эмпирически измеримо** через A/B-тест (см. метрики).

C (Self-Refine, одна LLM) не подходит, потому что наш аудитор гибридный (Phase 1 даёт findings, Phase 2 их триажит), и self-refine паттерн не использует структурированные findings.

D (полный Reflexion с памятью между сессиями) — overkill для хакатона.

## Реализация (ADR-0002 §3)

### Reflector-узел в LangGraph

```python
def reflector_node(state: LoopState) -> LoopState:
    audit = state["audit"]
    if audit.approved:
        return state
    prev_sql = state["sql_candidate"]
    findings = audit.vulnerabilities
    lessons = llm_reflect(prev_sql, findings)  # → list[Lesson]
    # Дедуп по rule_id, окно 5 последних
    reflection = state["reflection"] + lessons
    reflection = dedupe_by_rule_id(reflection)[-5:]
    return {**state, "reflection": reflection}
```

### Параметры reflector LLM

- **Модель**: `Qwen2.5-7B-Instruct` (а не 32B-Coder; см. ADR-0008 §1).
- **Temperature**: 0.1 (детерминированно).
- **Structured output**: JSON через `response_format={"type": "json_object"}`.
- **Validation**: Pydantic-схема `Lesson`; невалидный JSON игнорируется.

### В промпт generator'а

Системный промпт (ADR-0003 §3) включает блок «Reflection memory» с накопленными уроками.

### Дедупликация и окно

- Только 5 последних уникальных `lesson`-ов (deduped по `rule_id`).
- Это предохраняет от «зашумления»: генератор не перенастраивается под устаревшие правила.

## Что измеряем

**Самые важные метрики защиты:**

| Метрика | Цель | Что показывает |
|---|---|---|
| `iterations_used` median | ≤ 2 | Цикл быстро сходится |
| `approved_rate` | ≥ 0.85 | Цикл успешно одобряет |
| `risk_score_trajectory`: средняя дельта `risk@iter1 - risk@iterN` | ≥ 3.0 | Динамика снижения риска (требование ТЗ) |
| Recall@iter1 vs Recall@iterAny | ↑ на 5+ п.п. | Reflection добавляет покрытия |
| **% задач, где `vuln_class` repeats между итерациями** | **≤ 0.10** | **ПРЯМОЙ ОТВЕТ на исследовательский вопрос ТЗ** |
| EX with reflection vs without (A/B) | дельта ≥ +5 п.п. | A/B-тест архитектуры |

Эти данные → в Langfuse (ADR-0009), оттуда экспорт CSV → McNemar p-value → слайд презентации.

## Что может пойти не так

| Проблема | Митигация |
|---|---|
| Reflection «лечит симптом, не причину» (правит `SELECT *`, но забывает `LIMIT`) | В `lesson` включаем ВСЕ findings, не только верхнее |
| Конфликт `lesson`-ов между итерациями | Дедуп по `rule_id`, последний выигрывает |
| Длинная reflection-память забивает контекст | Лимит 5 + token budget cap |
| Reflector не успевает за 40 сек | Маленькая модель + параллельный вызов с подготовкой следующего промпта generator'а |
| Невалидный JSON от reflector | Pydantic + retry × 2; если и после — игнорируем lesson на эту итерацию |
| Reflector сам ошибается → плохой `lesson` уводит generator в тупик | A/B-тест с/без reflection даст численную оценку; если плохо — переключаем на baseline (вариант A — сырой `AuditResult`) |

## Связи с ADR

- **ADR-0002** §3 — Reflection-узел, контракт state.
- **ADR-0007** — методология измерения reflection-эффекта.
- **ADR-0008** — Reflector на Qwen 7B.
- **ADR-0009** — Langfuse trace per iteration.
