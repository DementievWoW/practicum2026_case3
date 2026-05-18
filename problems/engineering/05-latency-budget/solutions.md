# Варианты решения: Бюджет 40 секунд

## Альтернативные подходы

| # | Подход | Эффект | Стоимость | Решение |
|---|---|---|---|---|
| A | Hard timeout без бюджета токенов | Простой, но грубый | Низкая | ⚠️ baseline |
| B | **Per-run token + latency budget с graceful degradation** | Корректный finalize при превышении | Средняя | ✅ выбрали |
| C | Параллельные вызовы внутри узлов (async) | Экономия 2-5 сек на итерацию | Средняя инженерная | ✅ для критичных узлов |
| D | Self-consistency × 3 вместо × 5 | Экономия ~5 сек/iter | Низкая | ✅ |
| E | Reflector на Qwen-7B вместо 32B | Экономия 3-4 сек | Низкая (конфиг) | ✅ (см. ADR-0008) |
| F | Provider prefix-caching | До 50% на повторных запросах | Бесплатно (если провайдер умеет) | ✅ DeepInfra |
| G | Streaming в Streamlit | UX лучше, реальное время то же | Низкая | ✅ |
| H | Multi-judge consensus | × 3 латентность | Высокая | ❌ |
| I | Локальный vLLM с batching | Контроль latency полный | Высокая (GPU + ops) | вне MVP |

## Что выбрали и почему

**B + C + D + E + F + G** — комбинация низко-средне-стоимостных оптимизаций, дающих устойчивые ~22-35 сек медианных. H отбрасываем (×3 латентность). I — stretch goal на потом.

Ключевое решение — **B (budget с graceful degradation)**. Без него один upset-сценарий ломает демо.

## Реализация

### Бюджет per-run (ADR-0008 §4)

В `LoopState`:
```python
{
    "total_tokens_in": int,
    "total_tokens_out": int,
    "total_latency_seconds": float,
    "budget_exhausted": bool,
}
```

- `total_token_budget_per_run = 80_000` (in+out).
- `total_latency_budget_seconds = 45` (с запасом 5 сек).
- При превышении — `SystemResult.metadata.budget_exhausted = True`, finalize с лучшим из имевшихся SQL (last successful iteration).

### Параллельные вызовы внутри узлов

- **Phase 1 (auditor)**: все pglast Visitor-правила работают в один проход (single AST walk).
- **Phase 2 (auditor)**: RAG-fetch к Qdrant и подготовка промпта параллельно через `asyncio.gather`.
- **Reflector + Generator prep**: пока reflector обрабатывает findings от iter N, эмбеддим `task_description` для FAISS (не зависит от reflection).

### Self-consistency × 3

ADR-0003 §5: 3 семпла генератора, выбор по `pglast.parse_sql` валидности, далее proxy-критерий по similarity к few-shot. Экономия по сравнению с × 5 — ~5 сек.

### Reflector на Qwen 7B

Qwen2.5-7B-Instruct вместо 32B (ADR-0008 §1). Выигрыш ~3-4 сек.

### Provider prefix-caching

DeepInfra и OpenRouter поддерживают **prefix caching** автоматически. Повторяющийся system-prompt + few-shot между итерациями кешируется. До 50% на повторных запросах.

### Streaming в UI

Streamlit использует `cursor.stream_response` от LLM. Реальное время то же, но **воспринимается** быстрее.

### Cold-start mitigation

При старте сервера демо делаем **warm-up call** на каждый используемый model + endpoint. Документировано в скрипте запуска.

## Что измеряем

| Метрика | Цель | Где |
|---|---|---|
| p50 latency (медианное время цикла) | ≤ 25 сек | Langfuse trace |
| p95 latency | ≤ 40 сек | то же |
| p99 latency | ≤ 60 сек | то же |
| Доля задач с `budget_exhausted = true` | ≤ 5% | то же |
| Total tokens per run (p50) | ≤ 30K | то же |
| Cache hit rate (provider prefix caching) | ≥ 30% | provider API |

## Что может пойти не так

| Проблема | Митигация |
|---|---|
| Провайдер тормозит в день защиты | Secondary provider (OpenRouter ↔ DeepInfra), переключение через env-var |
| Cold start не успевает прогреться к демо | Launch script делает 3 warm-up call'а каждой модели за минуту до выхода жюри |
| Token budget exhausted на сложной задаче | Graceful degradation: `partial: true` с лучшим имеющимся SQL |
| Streaming не работает с self-host endpoint | Fallback на non-streaming с progress-bar |
| 5 итераций уходят в worst-case timeout | budget_exhausted + finalize; рассчитываем p99 ≤ 60 сек |

## Связи с ADR

- **ADR-0002** — архитектура цикла, бюджет в state.
- **ADR-0008** — выбор моделей (32B/7B баланс).
- **ADR-0009** — Langfuse как источник метрик latency.
