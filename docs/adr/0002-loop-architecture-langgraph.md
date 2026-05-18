# ADR-0002 — End-to-end architecture: generator↔judge loop on LangGraph

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** project owner

## Context

ТЗ (`tusk`, «Подробнее о задаче»):

> Предпочтительная архитектура — итеративный цикл «генератор → судья →
> исправление», однако команды могут предложить альтернативный подход,
> если он обеспечивает сопоставимый уровень безопасности и точности.

`baseline1.py` уже фиксирует контракты этого цикла:
`SQLSecuritySystem(generator, auditor, max_iterations=5).run(task)`,
с `IterationLog` и финальным `SystemResult`. Менять контракт нельзя —
мы интегрируемся в baseline.

Ментор (`take1`) рекомендует:

- Мультиагентка в **одном LLM-контуре** (не разносить по
  микросервисам).
- Варианты под эксперимент: один агент с тулами и циклом, master-slave
  с планировщиком, либо генератор + валидатор как независимые сущности.

Исследовательский вопрос ТЗ: «как сделать так, чтобы генератор
действительно учился на замечаниях судьи от итерации к итерации, а не
воспроизводил те же ошибки». Это явно мотивирует Reflexion-подобный
паттерн с памятью об ошибках.

Из обзора (`research/01_multiagent_text2sql.md`):

- **MAC-SQL** (COLING 2025) — ближайший прототип: Selector + Decomposer
  + Refiner с лимитом 3 итерации.
- **Reflexion** (NeurIPS 2023) — паттерн «memory-of-mistakes»: критик
  пишет короткий урок, который кладётся в контекст следующей попытки
  генератора. +22 % decision / +11 % code.
- **LangChain Reflection Agents + LangGraph SQL Agent** — готовые
  паттерны generator↔reflector в LangGraph (двухузловой MessageGraph).

Из (`research/03_deterministic_validators.md`) и
(`research/04_rag_knowledge_base.md`) видно: судья сам по себе ненадёжен
(IEEE 2025 — 100 % evasion линтеров), нужен гибрид. Это означает, что
один из узлов («auditor») внутри себя — не моно-LLM, а пайплайн
«детерминированные правила → RAG-судья → решение». Детали — ADR-0004
и ADR-0005.

## Decision

1. **Фреймворк оркестрации — LangGraph 0.2.x.** Граф вида:

   ```
                       ┌──────────────┐
                       │ schema_link  │  (ADR-0003)
                       └──────┬───────┘
                              │
                              ▼
   ┌──────────────┐     ┌──────────────┐
   │   reflect    │◄────│  generator   │  (ADR-0003, 0008)
   │  (memory of  │     └──────┬───────┘
   │   mistakes)  │            │
   └──────┬───────┘            ▼
          │             ┌──────────────┐
          │             │   auditor    │  (ADR-0004, гибрид:
          │             │              │   pglast + EXPLAIN +
          │             │              │   RAG-LLM)
          │             └──────┬───────┘
          │                    │
          │       approved? ───┴──── no ──► (reflect → generator)
          │                    │
          │                   yes
          │                    ▼
          │             ┌──────────────┐
          └──────────► │   finalize   │
                        └──────────────┘
   ```

   Лимит итераций — `max_iterations=5` (значение из
   `baseline1.SQLSecuritySystem.DEFAULT_MAX_ITERATIONS`).

2. **State (TypedDict для LangGraph)**:

   ```python
   class LoopState(TypedDict):
       task_description: str
       db_schema_meta: dict          # из schema_link, ADR-0003
       sql_candidate: str
       audit: AuditResult            # из baseline1
       iteration: int
       sql_history: list[str]
       reflection: list[str]         # «memory-of-mistakes», ADR-0002
       findings_static: list[dict]   # AST-правила, ADR-0004
       trace_id: str                 # для Langfuse, ADR-0009
   ```

3. **Reflection-узел** (отдельная LLM-роль, не сам генератор):
   на каждой итерации после провального аудита формирует
   1-3-предложение «правило на будущее» в формате:

   ```
   {"rule_id": "DML_NO_WHERE",
    "lesson": "Любой UPDATE/DELETE по таблице clients требует
               предиката по primary key — иначе судья отклонит."}
   ```

   Эти `lesson`-строки накапливаются в `state.reflection` и
   подаются в системный промпт генератора как «ошибки прошлых попыток
   — не повторяй». Прямой mapping из Reflexion на наш цикл — даёт
   измеримый ответ на исследовательский вопрос ТЗ.

4. **Узел `auditor`** не моно-LLM, а компонент с двумя
   фазами (детали — ADR-0004):

   - Фаза 1 (детерминированная): `pglast` AST + `EXPLAIN (FORMAT JSON)`
     → `list[Finding]`.
   - Фаза 2 (LLM-судья): принимает `findings_static` + SQL +
     RAG-контекст (CWE/CAPEC/OWASP, ADR-0005) → классифицирует,
     отсеивает FP, формирует `AuditResult` по контракту `baseline1`.

5. **MAC-SQL как референс-промпт**. Промпты Refiner адаптируем под
   security-feedback: вместо «вот ошибка исполнения, поправь» — «вот
   список уязвимостей с CWE/CAPEC-ID и рекомендациями, поправь».
   Selector и Decomposer из MAC-SQL — отдельные узлы graf-а
   (schema_link и при необходимости decomposer для сложных запросов).

6. **Persistence через `PostgresSaver`** (`langgraph-checkpoint-postgres`).
   Каждый super-step (узел) сохраняет `LoopState`. Детали — ADR-0009.

7. **`baseline1.SQLSecuritySystem.run()`** реализуется как тонкий
   адаптер: компилирует LangGraph, инвокает `graph.invoke(initial_state,
   config={"thread_id": session_id})`, мапит финальный `LoopState` в
   `SystemResult` из baseline.

## Consequences

**Положительные**

- Прямо отвечает на исследовательский вопрос ТЗ через Reflexion-память.
- Контракт `baseline1` сохранён → решение «втыкается» в платформу
  GreenData без переписывания вызывающего кода.
- `PostgresSaver` даёт time-travel: можно посмотреть состояние графа
  на любой итерации — это и есть «прозрачный лог аудита» из критериев
  оценивания (10 баллов).
- LangGraph встроенно интегрирован с Langfuse (`langfuse_handler` в
  `config.callbacks`) → бесплатный трейсинг (ADR-0009).
- Архитектура read как `Selector → Decomposer → Generator → Auditor
  → Reflector` — это знакомый паттерн (MAC-SQL/CHESS), легко защитить
  перед заказчиком.

**Отрицательные / Риски**

- LangGraph API нестабилен между минорами. **Pin'им
  `langgraph==0.2.x`** в `pyproject.toml`.
- Reflexion-память может «зашумляться» (генератор начинает
  переоптимизироваться под устаревшие уроки). Митигируем:
  ограничиваем `reflection` 5 последними записями + дедуп по
  `rule_id`.
- Persistence в Postgres = ещё один слой ответственности (миграции
  таблиц `langgraph_*`). Решено: те же миграции, что и для sandbox-DB
  (ADR-0001 / ADR-0004).
- LangGraph замыкает на экосистему LangChain — если позже захотим
  заменить на LlamaIndex/Haystack, миграция будет нетривиальной.

## Alternatives considered

| Альтернатива | Почему отказались |
|---|---|
| Своя FSM на чистом Python (без LangGraph) | Пишется за день, но теряем persistence, time-travel, интеграцию с Langfuse и checkpointers. На отчётность кейса повлияет негативно. |
| Master-slave с планировщиком (вариант ментора) | Излишен для MVP: единственная переменная управления — итерация генератор↔судья. Планировщик имеет смысл, когда задач >1 типа (генерация / EDA / визуализация). Это можно вынести в ADR позже. |
| Один агент с тулами (single ReAct loop) | Снижает прозрачность: на защите тяжело показать «вот критик, вот его замечание». Двухузловой граф даёт чистое разделение ролей и логирования. |
| MCS-SQL вместо итеративного цикла (N кандидатов → выбор) | Дороже по токенам и хуже совпадает с контрактом `baseline1.SystemResult` (там iterations_log, а не candidates). Можно использовать как «temperature sampling × 3» внутри узла generator — частный случай. |
| Pure Reflexion (без отдельного reflector-узла, generator сам пишет себе lesson) | В Self-Refine это работает, но в нашем случае reflector видит развёрнутые findings от детерминированного слоя — это другой контекст, чем у генератора. Отдельный узел чище. |

## Links

- ТЗ: `tusk` § «Подробнее о задаче», § «Ключевой исследовательский вопрос»
- Скелет: `baseline1.py` (`SQLSecuritySystem`, `IterationLog`,
  `SystemResult`, `DEFAULT_MAX_ITERATIONS = 5`)
- Обзор паттернов: `research/01_multiagent_text2sql.md` (Блок 1, 2, 3)
- MAC-SQL: https://arxiv.org/abs/2312.11242,
  https://github.com/wbbeyourself/MAC-SQL
- Reflexion: https://openreview.net/pdf?id=vAElhFcKW6
- LangGraph SQL Agent docs: https://docs.langchain.com/oss/python/langgraph/sql-agent
- LangChain Reflection Agents blog: https://blog.langchain.com/reflection-agents/
- Зависимые ADR: 0003 (generator), 0004 (auditor), 0005 (RAG),
  0008 (LLM), 0009 (persistence/observability)
