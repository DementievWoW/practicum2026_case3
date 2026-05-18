# 02 — Reflection-память: цикл реально учится

## Что

Цикл `генератор → судья → генератор` работает только если **на втором проходе генератор уже не повторяет ошибку**, на которой споткнулся на первом. Иначе мы получаем `max_iterations=5` итераций, каждая хуже предыдущей, и судья каждый раз отклоняет — **бесполезно**.

ТЗ (`tusk`) формулирует это как **главный исследовательский вопрос**:

> Ключевой исследовательский вопрос: как сделать так, чтобы генератор действительно учился на замечаниях судьи от итерации к итерации, а не воспроизводил те же ошибки?

И отдельным критерием с **25 баллами** («работа итеративного цикла»):

> Генератор действительно учитывает замечания судьи и исправляет запрос от итерации к итерации; одни и те же ошибки не воспроизводятся повторно.

## Почему критично

25 баллов — это **больше четверти от проходного порога (42 балла)**. Если цикл не учится — нечего показывать на защите, не на чем делать аналитику динамики риска (ещё 15 баллов).

Из обзора (`research/01_multiagent_text2sql.md` Блок 2):
- **Reflexion** (NeurIPS 2023): «verbal RL» — LLM-агент пишет себе reflection-память. +22% decision / +11% code.
- **Self-Refine**: одна LLM делает всё (генерация + критика + правка). +20% средне.
- **MAC-SQL** Refiner — наш ближайший прототип.

Все три работы говорят одно: **просто подать «вот ошибка» в промпт следующей итерации недостаточно**. Нужен **отдельный артефакт памяти** между итерациями.

## Силы, тянущие в разные стороны

| Куда тянет | Аргумент |
|---|---|
| **Подать сырой `AuditResult` в промпт** | Просто, никакой дополнительной логики |
| **Делать отдельный reflector-узел** | Лучшая абстракция; reflector видит то, что генератор бы пропустил |
| **Накапливать всю историю** | Полный контекст, не пропустим деталь |
| **Сжимать в короткий «урок»** | Не раздуть промпт; reflection устаревает |
| **Использовать ту же LLM** | Дешевле |
| **Использовать отдельную меньшую LLM** | Reflector задача проще, экономия |

## Наше решение (ADR-0002 §3)

### Отдельный узел `reflector` в LangGraph
Между `auditor` и `generator` (на retry-итерации) встроен узел:

```python
def reflector_node(state: LoopState) -> LoopState:
    audit = state["audit"]
    if audit.approved:
        return state  # nothing to reflect on
    prev_sql = state["sql_candidate"]
    findings = audit.vulnerabilities
    lessons = llm_reflect(prev_sql, findings)  # → list[Lesson]
    return {
        **state,
        "reflection": (state["reflection"] + lessons)[-5:],  # keep last 5
    }
```

### Формат `Lesson`
```python
@dataclass
class Lesson:
    rule_id: str       # например, "DML_NO_WHERE"
    lesson: str        # 1-3 предложения «не повторяй вот так»
    example_bad: str   # фрагмент проблемного SQL
    example_good: str  # как должно было быть
```

### В системный промпт `generator`
```
### Reflection memory (lessons from previous attempts)
- [DML_NO_WHERE] Любой UPDATE/DELETE по таблице clients требует predicate по PK.
  Плохо:  UPDATE clients SET balance = 0
  Хорошо: UPDATE clients SET balance = 0 WHERE client_id = $1

- [SELECT_STAR] В отчётах по PII-таблицам никогда не используй SELECT *.
  Плохо:  SELECT * FROM clients
  Хорошо: SELECT id, full_name, email FROM clients
- ...
```

### Reflector — отдельная LLM (Qwen 7B)
Задача reflector'а проще, чем у generator'а: видит готовые findings, не пишет SQL. Перевод на Qwen 7B экономит x4-5 на токенах (ADR-0008).

### Дедупликация и временное окно
- `reflection` хранит **5 последних** уникальных `lesson`-ов (deduped по `rule_id`).
- Это предохраняет от «зашумления» — генератор не перенастраивается под устаревшие правила.

## Trade-off

**Риск:** reflector сам ошибается → плохой `lesson` уводит генератор в тупик. Митигации:
1. `temperature=0.1` для reflector — детерминированно.
2. Validate-схема (Pydantic) — `Lesson` должен парситься как JSON, иначе игнорируется.
3. **A/B тест с/без reflection** в eval-set (ADR-0007) — измеряем, действительно ли цикл сходится быстрее.

## Что измеряем

Это **самые важные метрики защиты**:

| Метрика | Цель | Что показывает |
|---|---|---|
| **`iterations_used` median** | ≤ 2 | Цикл быстро сходится |
| **`approved_rate`** | ≥ 0.85 | Цикл успешно одобряет |
| **`risk_score_trajectory`**: средняя дельта `risk@iter1 - risk@iterN` | ≥ 3.0 | Динамика снижения риска (требование ТЗ) |
| **Recall@iter1 vs Recall@iterAny** | ↑ на 5+ п.п. | Reflection добавляет покрытия |
| **% задач, где `vuln_class` repeats** между итерациями | ≤ 0.10 | **ПРЯМОЙ ОТВЕТ на исследовательский вопрос ТЗ** |
| **EX with reflection vs without** | дельта ≥ +5 п.п. | A/B-тест архитектуры |

Эти данные → в Langfuse (ADR-0009), оттуда экспорт CSV → McNemar p-value → слайд презентации.

## Связи

- **ADR-0002** §3 — Reflection-узел.
- **ADR-0007** — методология измерения reflection-эффекта.
- **ADR-0008** — Reflector на Qwen 7B.
- **ADR-0009** — Langfuse trace per iteration.
- **research/01_multiagent_text2sql.md** Блок 2 — Reflexion, Self-Refine, ReFoRCE.
- **research/materials/02-critics-self-correction/retrysql/** — Retry data для самокоррекции.
- **research/materials/02-critics-self-correction/r3-review-rebuttal-revision/** — трёхфазный consensus как альтернативный паттерн.
- **research/materials/02-critics-self-correction/errorllm/** — специализированная LLM для моделирования ошибок.

## Что может пойти не так

1. **Reflection «лечит симптом, не причину»** — судья нашёл `SELECT *`, reflector написал «не используй *», на следующей итерации генератор подменяет `*` явным списком, но забыл `LIMIT`. Новая итерация. Митигация: в `lesson` включаем ВСЕ findings, не только верхнее.
2. **Конфликт `lesson`-ов** — на итер 1: «добавь WHERE», на итер 2: «не используй complex WHERE». Митигация: дедуп по `rule_id`, последний выигрывает.
3. **Длинная reflection-память** забивает контекст. Митигация: лимит 5 + token budget cap.
4. **Reflector не успевает за 40 сек** (см. [05-latency-budget](../05-latency-budget/)). Митигация: маленькая модель + параллельный вызов с подготовкой следующего промпта generator'а.
