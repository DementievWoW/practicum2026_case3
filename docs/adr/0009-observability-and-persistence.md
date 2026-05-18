# ADR-0009 — Observability and state persistence: Langfuse + PostgresSaver

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** project owner

## Context

ТЗ (`tusk`) — два прямых требования к логированию:

- «Реализовать **прозрачный лог** для пользователя: какие риски были
  обнаружены, сколько итераций потребовалось, почему финальный
  запрос признан безопасным.» (10 баллов «Прозрачность для
  пользователя»).
- «Аналитика и отчётность: динамика оценки риска по итерациям,
  среднее число итераций до одобрения и содержательный анализ
  ошибок.» (15 баллов).

Архитектура (ADR-0002) — LangGraph с 4+ узлами (schema_link,
generator, auditor, reflector, finalize) и циклом до 5 итераций.
Без инструментирования аналитика и аудит-лог придётся писать руками,
дублируя работу.

Из `research/05_peripheral.md`:

- **LangGraph persistence** — встроенные checkpointers
  (`MemorySaver`, `SqliteSaver`, `PostgresSaver`,
  `MongoDBSaver`). Каждый super-step сохраняется → time-travel,
  fault-tolerance, human-in-the-loop.
- **Langfuse** — open-source, self-host, OpenAI-instrumentation,
  scoring/evals/datasets/AB-тесты в одном продукте, ложится на
  LangGraph callbacks.
- **LangSmith** — официальная интеграция LangChain, но платная и
  данные уходят к LangChain Inc.

Из `take1` (ментор) исследовательский вопрос ТЗ:

> как сделать так, чтобы генератор действительно учился на замечаниях
> судьи от итерации к итерации, а не воспроизводил те же ошибки?

Без подробного трейсинга на этот вопрос невозможно ответить
эмпирически (мы должны видеть: какие ошибки судья нашёл на итер. 1,
что reflector сохранил в lesson, что генератор взял в промпт на
итер. 2, какие ошибки судья нашёл на итер. 2). Это именно то, что
обещает Langfuse + LangGraph state.

## Decision

1. **State persistence — `PostgresSaver`**
   (`langgraph-checkpoint-postgres`).

   - Тот же PostgreSQL-инстанс, что и sandbox-БД (ADR-0004), но
     отдельная схема `case3_state`. Это упрощает деплой (один
     сервис).
   - Каждый run цикла идентифицируется `thread_id = session_id`
     из UI. Каждый super-step сохраняет полный `LoopState`
     (ADR-0002).
   - Время жизни — 30 дней (cleanup-задание раз в сутки), для демо
     достаточно.
   - Time-travel: на CLI/Streamlit добавляется кнопка «Открыть
     лог сессии» с `session_id` → восстановление любой итерации.

2. **Observability — Langfuse self-host**:

   - Docker-compose поверх той же инфры: `langfuse-server`,
     `clickhouse`, `redis`, `minio` (стандартный stack v3).
     Один volume под persistent storage.
   - Подключение через `langfuse-langchain` → `CallbackHandler`,
     передаётся в `graph.invoke(..., config={"callbacks":[handler]})`.
     LangGraph автоматически трассирует все узлы и LLM-вызовы.
   - Тэгирование trace:
     - `user_id = session_id`
     - `tags = ["case3", model_name, env]` (например, `env="eval"`,
       `env="demo"`)
     - `metadata = {task_difficulty, total_iterations,
                    final_risk, approved}`

3. **Семантика трейсов** — каждый run цикла:

   ```
   trace: case3.run
     ├─ span: schema_link
     │    ├─ embedding (batch)
     │    └─ FAISS retrieval
     ├─ iter 1
     │    ├─ span: generator
     │    │     └─ LLM call (Qwen, prompt, output, tokens)
     │    ├─ span: auditor.phase1 (pglast, EXPLAIN)
     │    │     └─ findings: [...]
     │    ├─ span: auditor.phase2 (LLM-judge)
     │    │     └─ LLM call + RAG retrieval (Qdrant)
     │    └─ score: overall_risk_score, approved
     ├─ iter 2
     │    ├─ span: reflector
     │    │     └─ LLM call → lesson
     │    └─ ... (как iter 1)
     └─ span: finalize
   ```

   Это даёт визуально проверяемый ответ на исследовательский вопрос
   ТЗ: можно открыть один trace и увидеть, как `lesson` от
   reflector'а на итер.1 попал в системный промпт generator'а на
   итер.2 и привёл к снижению `overall_risk_score`.

4. **Scores и метрики**:

   - **Per-run scores в Langfuse**:
     - `execution_accuracy` (бинарно, ставится eval-pipeline'ом, см.
       ADR-0007)
     - `soft_f1` (float, eval)
     - `final_approved` (bool)
     - `iterations_count` (int)
     - `latency_seconds` (float)
   - **Aggregate metrics** считаются Langfuse через UI или
     `Datasets API`. Это закрывает критерий «Аналитика и отчётность»
     визуально, без необходимости писать дашборд руками.

5. **Eval-pipeline (ADR-0007) использует Langfuse `Datasets`**:

   - Загружаем `data/dataset_v1.jsonl` (через `langfuse.create_dataset_item`).
   - Запускаем `dataset.run(name="qwen-coder-32b-with-rag")` →
     каждая задача = trace, scores автоматически прикреплены.
   - В UI Langfuse: сравнение двух runs (например, with/without
     reflection) с диффом per-example. **Это и есть наш A/B
     инструмент** (см. ADR-0007 stat-test поверх этих данных).

6. **Audit log для пользователя** (требование ТЗ «Прозрачный лог»):

   - Streamlit-демо берёт `trace_id` из `state.trace_id`, формирует
     ссылку `https://langfuse.local/trace/{trace_id}`.
   - Дополнительно — рендерит «человеческий» отчёт в UI:
     - Финальный SQL с подсветкой.
     - Таблица: `iteration | found_vulnerabilities | risk_score |
                 lesson_for_next_iter`.
     - Итоговый вердикт и summary.
   - Экспорт `SystemResult` в JSON + рендер в markdown — закрывает
     «лог аудита» из артефактов ТЗ.

7. **Окружения**:

   - `dev` — Langfuse self-host, in-memory state (`MemorySaver`)
     для unit-тестов, `PostgresSaver` для интеграционных.
   - `defense` — `PostgresSaver` обязательно, Langfuse self-host
     обязательно (на проекторе показываем trace).
   - `eval` — `PostgresSaver`, Langfuse `dataset run`.

8. **Не использовать LangSmith** в основном пайплайне. Если жюри
   захочет посмотреть LangSmith — добавим как опциональный handler
   (LangGraph поддерживает multi-callback).

## Consequences

**Положительные**

- Закрываются два критерия (Прозрачность 10 + Аналитика 15 = 25
  баллов) одной интеграцией.
- Self-host Langfuse → данные не уходят в облако, заказчик
  доволен (важно для GreenData, российский корпоративный сектор).
- Time-travel на PostgresSaver → можно показать «вот была
  итер.2, посмотрим, что произошло, если изменить промпт».
- Один Postgres-инстанс на sandbox + state — упрощает деплой.

**Отрицательные / Риски**

- Langfuse stack (langfuse-server + clickhouse + redis + minio) —
  4 контейнера. Тяжело для разработческой машины. Митигируем:
  использование `langfuse:3-cloud-lite` (single container) на
  dev-окружении.
- `PostgresSaver` блокирует на длинных LLM-вызовах если использовать
  sync API. Используем async-вариант (LangGraph поддерживает
  `await graph.ainvoke`).
- Один Postgres для state + sandbox + Langfuse Postgres-storage
  — нагрузка на один сервис. Для defence-демо это ок; в продакшене
  будет ADR на разделение.
- Если Langfuse self-host упадёт во время демо, цикл не сломается
  (`callbacks` — best-effort), но мы потеряем визуальный аргумент.
  Митигируем: на defence-демо запускаем Langfuse за 30 минут до
  выступления и проверяем `/api/health`.

## Alternatives considered

| Альтернатива | Почему отказались |
|---|---|
| LangSmith (платный SaaS) | Данные уходят к LangChain Inc.; для российского заказчика — риск. |
| OpenLLMetry + Phoenix | Phoenix хорош, но требует второй интеграции (отдельно метрики, отдельно scoring). Langfuse решает всё в одном UI. |
| Свой логгер на JSONL-файлах | Дешёво, но нет UI для жюри; tracing-tree вручную не нарисовать. |
| Без persistence (MemorySaver) | Теряем time-travel; цикл не возобновляется после рестарта. Защита проиграется при первом сбое. |
| SqliteSaver | Подойдёт для dev, но для defence-демо хочется одну инфру; PostgreSQL у нас уже есть. |
| MongoDBSaver (с cross-thread / vector search) | Перебор: cross-thread мы не используем, у нас одна сессия = один thread_id. |
| Хранить state в Langfuse-метадате (без LangGraph persistence) | Langfuse — не state store; не предоставляет time-travel API. Это backwards-incompatible идея. |

## Links

- ТЗ: `tusk` § «Прозрачный лог для пользователя»,
  § «Критерии оценивания» (Прозрачность 10, Аналитика 15)
- Обзор: `research/05_peripheral.md` § 5 «LangGraph state
  persistence + observability»
- LangGraph persistence: https://docs.langchain.com/oss/javascript/langgraph/persistence
- Langfuse self-host: https://langfuse.com/self-hosting
- Langfuse + LangGraph cookbook:
  https://langfuse.com/guides/cookbook/example_langgraph_agents
- Langfuse A/B testing:
  https://langfuse.com/docs/prompt-management/features/a-b-testing
- Зависит от: ADR-0001 (стек), ADR-0002 (state контракт),
  ADR-0007 (eval scores), ADR-0008 (LLM-traces)
