# 05 — Бюджет латентности 40 секунд

## Что

В `take1` ментор: «Эффективность (токены, время — **лимит 40 секунд**)».

Это **мягкое ограничение** (не из официального ТЗ), но реалистичная цель для live-demo: жюри не будет ждать минуту, пока цикл сходится. Если демо «зависает» на 90 сек — мы теряем 10 баллов «Качество live-demo и презентации» и подрываем доверие к архитектуре.

## Почему критично

10 баллов сами по себе не блокирующие, но:
- Live-demo — это первое, что видят жюри. Если оно тормозит — общее впечатление ниже, бьёт по интегральной оценке.
- Если на eval-pipeline один запуск занимает > 40 сек, мы не успеваем прогнать 60 примеров за разумное время → не можем сделать A/B-тест за день перед защитой.

## Что входит в 40 секунд

Один запуск цикла с **средней `iterations_used = 2`**:

| Узел | Время | Что внутри |
|---|---|---|
| schema_link | ~0.5 сек | FAISS top-15 + FK closure |
| generator (iter 1) | **~5-10 сек** | LLM Qwen-Coder 32B, in 20K / out 600 tokens |
| auditor Phase 1 (iter 1) | ~1 сек | pglast AST + EXPLAIN sandbox |
| auditor Phase 2 (iter 1) | **~3-5 сек** | LLM Qwen-Coder 32B как judge + RAG fetch |
| reflector (iter 1→2) | ~1-2 сек | Qwen 7B компактный |
| generator (iter 2) | ~5-10 сек | повтор |
| auditor (iter 2) | ~4-6 сек | повтор |
| finalize | < 0.5 сек | сборка SystemResult |
| **Сумма** | **~22-35 сек** | **в бюджете** |

При `iterations_used = 5` (худший случай) — **~60 сек**, превышает. Митигации — ниже.

## Силы, тянущие в разные стороны

| Куда тянет | Аргумент |
|---|---|
| **Большая модель (32B)** | Качество выше |
| **Маленькая модель (7B)** | Быстрее, дешевле |
| **Длинный few-shot (10 примеров)** | Качество выше |
| **Короткий few-shot (3)** | Меньше токенов, быстрее |
| **Multi-judge consensus** | Точнее |
| **Single-judge** | В разы быстрее |
| **`self_consistency=5` семплов** | Лучше топ-1 |
| **`self_consistency=1`** | Быстрее |
| **Запросы последовательно** | Просто |
| **Запросы параллельно** | Дороже в инженерии, но в 2-3x быстрее |

## Наше решение (ADR-0002 + ADR-0008 + ADR-0009)

### Бюджет per-run

В `LoopState` хранится:
```python
{
    "total_tokens_in": int,
    "total_tokens_out": int,
    "total_latency_seconds": float,
    "budget_exhausted": bool,
}
```

- `total_token_budget_per_run = 80_000` (см. ADR-0008 §4).
- `total_latency_budget_seconds = 45` (с запасом 5 сек).
- При превышении — `SystemResult.metadata.budget_exhausted = True`, finalize с лучшим из имевшихся SQL.

### Параллельные вызовы внутри узлов

**Phase 1 (auditor):** все pglast Visitor-правила работают независимо, можно гонять в один проход через `pglast.visitors.Visitor` (один обход AST) или параллельно через `multiprocessing.Pool` (overkill для 11 правил, не делаем).

**Phase 2 (auditor LLM):** RAG-fetch к Qdrant и подготовка промпта — параллельно через `asyncio.gather`. Экономит ~0.5-1 сек.

**Reflector + Generator (iter N+1) prep:** пока reflector думает над findings от iter N, мы заранее эмбеддим `task_description` для FAISS (не зависит от reflection). Маленькая, но экономия.

### Self-consistency × 3, не × 5

ADR-0003 §5: 3 семпла генератора, выбор по `pglast.parse_sql` валидности. Дальше — выбор «похожего на few-shot» проксированием. Экономия по сравнению с × 5 — ~5 сек на каждый запуск.

### Reflector на маленькой модели

Qwen2.5-7B-Instruct вместо 32B (ADR-0008 §1). Reflector задача — переписать findings в короткие lesson-ы. 7B справляется, выигрыш ~3-4 сек.

### Кеш промптов

DeepInfra и OpenRouter поддерживают **prefix caching**: повторяющийся system-промпт + few-shot между итерациями кешируется. Это даёт **до 50% на повторных запросах**. Без явных действий, провайдер делает сам, если поддерживает.

### Streaming в UI

Streamlit-демо использует `cursor.stream_response` от LLM. UX лучше, реально время такое же, но **воспринимается** быстрее. Психологический трюк.

### Cold-start mitigation

Первый вызов LLM-провайдера часто медленный (5-10 сек). При старте сервера демо делаем **warm-up call** на каждый используемый model + endpoint. Документировано в скрипте запуска.

## Trade-off

**Жертвуем:** некоторое качество (self_consistency 3 vs 5, reflector 7B vs 32B).
**Получаем:** укладываемся в 40 сек на 95% задач (median 2 итерации).

Worst-case (5 итераций) выходит за лимит — на это есть `budget_exhausted` флаг и graceful degradation.

## Что измеряем

| Метрика | Цель | Где |
|---|---|---|
| **p50 latency** (медианное время цикла) | ≤ 25 сек | Langfuse trace |
| **p95 latency** | ≤ 40 сек | то же |
| **p99 latency** | ≤ 60 сек | то же |
| **Доля задач с `budget_exhausted = true`** | ≤ 5% | то же |
| **Total tokens per run (p50)** | ≤ 30K | то же |
| **Cache hit rate** (provider prefix caching) | ≥ 30% | provider API |

## Связи

- **ADR-0002** — архитектура цикла (бюджет в state).
- **ADR-0008** — выбор моделей (32B/7B баланс).
- **ADR-0009** — Langfuse как источник метрик latency.
- **research/05_peripheral.md** § 2 — цены и latency провайдеров.
- **research/materials/02-critics-self-correction/** — паттерны самокоррекции (некоторые быстрее).

## Что может пойти не так

1. **Провайдер тормозит** в день защиты. Митигация: secondary provider (OpenRouter ↔ DeepInfra), переключение через env-var.
2. **Адресный pre-warm cold start** не успевает прогреться к моменту демо. Митигация: launch script делает 3 warm-up call'а каждой модели за минуту до выхода жюри.
3. **Token budget exhausted на сложной задаче** (например, очень длинный промпт + reflection-память). Митигация: graceful degradation возвращает `partial: true` с лучшим имеющимся SQL.
4. **Streamlit streaming не работает с self-host endpoint** (некоторые провайдеры не поддерживают SSE). Митигация: fallback на non-streaming с progress-bar по фейковому шагу.
