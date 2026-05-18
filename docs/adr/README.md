# Architecture Decision Records — practicum2026_case3

Журнал архитектурных решений по проекту «GreenData SQL Security System»
(МФТИ Practicum 2026, кейс 3): мультиагентная генерация и аудит SQL-запросов
для PostgreSQL.

## Принципы ведения

- Каждое решение — отдельный файл `NNNN-kebab-title.md` в нумерации `0001`,
  `0002`, ... ADR никогда не удаляется и не «правится по сути». Если решение
  пересматривается, **создаётся новый ADR**, который ссылается на старый и
  меняет статус старого на `Superseded by NNNN`.
- Шаблон: **Context**, **Decision**, **Status**, **Consequences**,
  **Alternatives**, **Links**.
- Все технические заявления в ADR должны быть подтверждены конкретным
  материалом из `research/0?_*.md` или ссылкой на исходник в репозитории
  (`baseline1.py`, `data_model_sql/data_model.sql`, `case_3.txt`, `tusk`,
  `take1`). Если решение опирается на внешнюю работу — даём прямую ссылку
  в **Links**.

## Индекс

| № | Заголовок | Статус |
|---|---|---|
| 0001 | [Toolchain and Python environment](0001-toolchain-and-environment.md) | Accepted |
| 0002 | [End-to-end architecture: generator↔judge loop on LangGraph](0002-loop-architecture-langgraph.md) | Accepted |
| 0003 | [SQL generator: prompt-engineering with schema linking, no fine-tuning](0003-generator-prompt-engineering.md) | Accepted |
| 0004 | [Hybrid auditor: deterministic AST checks + LLM as triager](0004-hybrid-auditor-ast-plus-llm.md) | Accepted |
| 0005 | [RAG knowledge base structure for the judge](0005-rag-knowledge-base.md) | Accepted |
| 0006 | [Dataset synthesis via SQL-to-Text back-translation](0006-dataset-back-translation.md) | Accepted |
| 0007 | [Execution Accuracy methodology and evaluator safety](0007-execution-accuracy-methodology.md) | Accepted |
| 0008 | [LLM choice and inference provider](0008-llm-choice-and-provider.md) | Accepted |
| 0009 | [Observability and state persistence: Langfuse + PostgresSaver](0009-observability-and-persistence.md) | Accepted |
| 0010 | [PL/pgSQL audit path via plpgsql_check (bonus track)](0010-plpgsql-bonus-path.md) | Accepted |

Дальше по мере прохождения пайплайна (схема-каталог → промпт-каркас →
аудитор → датасет → метрики → демо) будут добавляться ADR-0011+.
