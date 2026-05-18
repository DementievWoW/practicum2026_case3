# Круг 5 — Косвенные материалы

Периферийное, но даёт «дешёвые вина» на защите.

## 1. SQL-to-Text как back-translation для синтеза датасета

Идея: вместо ручной разметки NL→SQL — берём готовые SQL и просим LLM сгенерировать NL-вопрос.

### OmniSQL (VLDB 2025) ⭐
- arXiv: https://arxiv.org/html/2503.02240v2
- PDF: https://www.vldb.org/pvldb/vol18/p4695-li.pdf
- Repo: https://github.com/RUCKBReasoning/OmniSQL
- **SynSQL-2.5M** — первый миллион-масштабный датасет: 2.5M примеров, 16K синтетических БД, каждый пример = схема + SQL + NL + CoT.
- Авторы прямо обосновывают: «SQL-to-Text более стабилен из-за гибкости естественного языка».
- Модели OmniSQL 7B/14B/32B полностью открыты.

### SING-SQL (2025)
- arXiv: https://arxiv.org/html/2509.25672v1
- Complexity-controlled SQL synthesis → LLM-as-judge validation → executability check → SQL repair → reasoning traces.
- Парафразирование в разных стилях.

### Промпт-паттерн back-translation

> «Сначала объясни SQL пошагово, затем сформулируй короткий NL-вопрос пользователя, который привёл бы к этому SQL. Верни JSON: {explanation, question, difficulty}.»

Бонус: CoT-рационалы пишутся параллельно. **CODES** делает би-направленную аугментацию: SQL→шаблонный вопрос→LLM-перефраз.

### Применение в кейсе

Взять 200 реальных SQL по схеме GreenData → GPT-4o-mini back-translate → 200 NL-задач за пару долларов. **Это домен-специфичный eval-set.**

## 2. Сравнение код-моделей до 32B

### Qwen2.5-Coder 32B ⭐
- Tech report: https://arxiv.org/html/2409.12186v3
- HumanEval 88.4% (выше GPT-4 87.1%); 5.5T code-токенов (×5 vs DeepSeek).
- Выигрывает на SWE-bench и LiveCodeBench.
- На SQL — топ-3 в Tinybird и Beekeeper Studio бенчах.

### DeepSeek-Coder V2
- Full 236B MoE выигрывает HumanEval.
- V2-Lite 16B (≈2.4B active) — про скорость; accuracy ниже Qwen 32B.

### StarCoder2 — отстаёт по SQL, остаётся baseline для fine-tune.

### Цены за 1M токенов (input/output, май 2026)

| Провайдер | Qwen2.5-Coder-32B |
|---|---|
| OpenRouter | $0.66 / $1.00 |
| DeepInfra | ~$0.66 / ~$0.66 |
| Together AI | $0.80 / $0.80 |
| Fireworks | дороже, низкая latency |

**Рекомендация:** DeepInfra или OpenRouter + Qwen2.5-Coder 32B. Для judge — та же или Qwen 7B (×4-5 дешевле).

### Источники
- [Qwen vs DeepSeek (Markaicode)](https://markaicode.com/vs/qwen-2-5-coder-vs-deepseek-coder/)
- [Open-Source LLMs Compared 2026](https://till-freitag.com/en/blog/open-source-llm-comparison)
- [OpenRouter Qwen pricing](https://openrouter.ai/qwen/qwen-2.5-coder-32b-instruct)
- [DeepInfra Qwen pricing 2026](https://deepinfra.com/blog/qwen-api-pricing-2026-guide)
- [Together AI Pricing](https://www.together.ai/pricing)
- [Tinybird LLM SQL Benchmark](https://www.tinybird.co/blog/which-llm-writes-the-best-sql)
- [Beekeeper SQL AI Codegen](https://www.beekeeperstudio.io/blog/sql-ai-codegen-benchmarks)

## 3. A/B-тестирование LLM-систем

Корректный A/B на фиксированном eval-set (≥50-200, идеал 300+).
Метрики для аудитора: Execution Accuracy, Exact Match, judge-score, FP-rate уязвимостей, длина цикла, стоимость.

### Стат-критерии (важно для защиты!)

- **McNemar's test** — золотой стандарт для парного бинарного сравнения (правильно/неправильно) на одной выборке.
  - https://machinelearningmastery.com/mcnemars-test-for-machine-learning/
- **Paired bootstrap test** — для непрерывных метрик (judge-score, BLEU). Ресэмпл 1000+ раз, CI разности.
  - https://medium.com/ai-enthusiast/comparing-nlp-models-with-confidence-the-paired-bootstrap-test-explained-c9a88532ea3d
- ≥3 систем — **Cochran's Q** или Bonferroni.
  - https://machinelearningmastery.com/statistical-significance-tests-for-comparing-machine-learning-algorithms/

### Инструменты

- **Langfuse** ⭐ — встроенный A/B в prompt management, open-source, self-host, ложится на LangGraph.
  - https://langfuse.com/docs/prompt-management/features/a-b-testing
  - https://pub.towardsai.net/evaluating-and-monitoring-llms-with-langfuse-a-b-testing-metrics-bddea6e51574
- **Arize Phoenix** — быстрее в логировании (~41с vs Langfuse 119с в бенче Comet).
- **OpenLLMetry** — OpenTelemetry-совместимые спаны.
  - https://langfuse.com/guides/cookbook/otel_integration_openllmetry

**Хакатонный минимум:** Langfuse self-host + 100 NL→SQL → 2 Experiments → McNemar/bootstrap в ноутбуке → скриншот в презу.

## 4. Live-demo (Streamlit / Gradio)

### Streamlit + streamlit-ace ⭐
- https://github.com/okld/streamlit-ace
- https://pypi.org/project/streamlit-ace/
- Ace-редактор, темы monokai/github, language=sql, real-time editing.

### Streamlit-code-editor (bouzidanas)
- https://github.com/bouzidanas/streamlit-code-editor
- React-ace + кастомные кнопки поверх редактора (например, «Run audit»).

### Каркас демо

1. `st.text_area` — NL-запрос.
2. `st_ace(language="sql", theme="monokai")` — сгенерированный SQL (редактируемый).
3. `st.expander("Audit log")` — timeline судьи: каждый turn = `st.chat_message`, цветная метка severity.
4. Подсветка уязвимостей: regex/sqlparse → HTML с `<mark>` или Streamlit color-text `:red[SQL Injection]` / `:orange[Missing WHERE]`.
5. `st.metric` для KPI (стоимость, latency, итерации).

### Gradio vs Streamlit
- https://evidence.dev/learn/gradio-vs-streamlit
- Gradio быстрее в построении, Streamlit удобнее для «дашбордового» вида.
- Учитывать CVE: Gradio имел 11 CodeQL-уязвимостей; Streamlit — CVE в `st.file_uploader` (≥1.43.2). Упомянуть на защите: «в демо отключены user-uploads/code-exec — security by design».

## 5. LangGraph state persistence + observability

### Persistence
- Docs: https://docs.langchain.com/oss/javascript/langgraph/persistence
- LangGraph встроенно сохраняет состояние графа как **checkpoints** на каждом super-step.
- Даёт human-in-the-loop, conversational memory, **time-travel debugging**, fault-tolerance.
- **Критично для возобновления прерванного цикла.**
- Чекпоинтеры: `MemorySaver` (dev), `SqliteSaver`, **`PostgresSaver`** (`@langchain/langgraph-checkpoint-postgres`, прод), `MongoDBSaver`.

### Observability

- **LangSmith** — официальная интеграция, визуализация графа, runtime-метрики. Платная.
- **Langfuse** ⭐ — open-source, self-host. `langfuse_handler` передаётся в `agent.invoke(..., config={"callbacks":[handler]})`. Scoring/evals/датасеты — закрывает A/B из п.3.
  - Cookbook: https://langfuse.com/guides/cookbook/example_langgraph_agents
  - Cookbook: https://langfuse.com/guides/cookbook/integration_langgraph

### Для отчётности кейса (требование!)
Persistence-thread_id = session_id из UI → каждый запуск аудита фиксирует все turn'ы в Langfuse. Экспорт CSV/JSON прямо из UI = готовый аудит-журнал.

## 6. PL/pgSQL и хранимые процедуры в LLM (бонус +10)

Открытых публикаций мало — **возможность отличиться**.

### EPAM Code Migration Framework
- https://solutionshub.epam.com/blog/post/code-migration
- Fine-tuned LLM мигрируют PL/SQL → PL/pgSQL, покрытие 58–69% (низко из-за процедурной логики).
- `Qwen32B-ft2` достиг 72.3% по CORE_SQL.
- **Вывод**: голым LLM покрытие посредственное, нужен fine-tune + многошаговый цикл с компилятором.

### SQLGenie (ACL 2025 Industry)
- https://aclanthology.org/2025.acl-industry.71.pdf
- Компилятор/executor как внешний оракул в judge-loop. Адаптируется под `plpgsql_check`.

### BIRD-Interact — интерактивный бенч с PL/pgSQL фрагментами.

### Что добавить в кейс (быстро)

1. Парсер `CREATE OR REPLACE FUNCTION ... LANGUAGE plpgsql` → отдельный путь.
2. Прогон через **`plpgsql_check`** (https://github.com/okbob/plpgsql_check):
   - SQL-injection в `EXECUTE`.
   - Неиспользуемые переменные.
   - Mismatched return types.
3. Judge-промпт расширить чек-листом:
   - SECURITY DEFINER без `SET search_path`.
   - Динамический `EXECUTE` с конкатенацией.
   - Отсутствие `EXCEPTION WHEN OTHERS`.
   - `RAISE` без severity.
4. В отчёте — **отдельный режим «Stored Procedure Auditor»**. Это и есть «бонус».

## Топ-3 «дешёвых вина» для защиты ⭐

### 1. Back-translation eval-set + McNemar в презе
- 100-200 SQL из открытого корпуса → GPT-4o-mini back-translate → eval-set.
- Запуск двух версий пайплайна (baseline vs наш) → McNemar p-value.
- На слайде: «наша система статистически значимо лучше baseline (p<0.01)».
- **Впечатляет жюри сильнее любой архитектуры.**
- Стоимость: ~$5, 2 часа.

### 2. Langfuse self-host + полный аудит-трейс в UI
- Docker за 10 минут → `langfuse_handler` к LangGraph → кнопка «Открыть трейс в Langfuse» в Streamlit.
- Закрывает требование кейса по «логированию для отчётности».
- Корпоративная зрелость. Бесплатно.

### 3. PL/pgSQL-режим через `plpgsql_check`
- +10 баллов за один интеграционный шаг.
- Детектим `LANGUAGE plpgsql` → отдельный prompt-чек-лист + `plpgsql_check` как tool в judge-loop → отдельная вкладка в демо.
- **Закрывает явный бонус из ТЗ.**

## Источники

- [SING-SQL](https://arxiv.org/html/2509.25672v1)
- [OmniSQL arXiv](https://arxiv.org/html/2503.02240v2) · [OmniSQL VLDB PDF](https://www.vldb.org/pvldb/vol18/p4695-li.pdf) · [OmniSQL GitHub](https://github.com/RUCKBReasoning/OmniSQL)
- [NL2SQL Handbook](https://github.com/HKUSTDial/NL2SQL_Handbook)
- [LLM Data Synthesis &amp; Distillation (Springer)](https://link.springer.com/chapter/10.1007/978-981-95-0014-7_5)
- [Qwen2.5-Coder Tech Report](https://arxiv.org/html/2409.12186v3)
- [SQLGenie ACL'25 Industry](https://aclanthology.org/2025.acl-industry.71.pdf)
- [EPAM PL/SQL → PL/pgSQL](https://solutionshub.epam.com/blog/post/code-migration)
- [BIRD-bench](https://bird-bench.github.io/)
- [Langfuse A/B Testing](https://langfuse.com/docs/prompt-management/features/a-b-testing)
- [Langfuse LangGraph cookbook](https://langfuse.com/guides/cookbook/integration_langgraph)
- [Langfuse OpenLLMetry](https://langfuse.com/guides/cookbook/otel_integration_openllmetry)
- [Comet — LLM Eval Frameworks](https://www.comet.com/site/blog/llm-evaluation-frameworks/)
- [Top LLM Observability Tools 2025](https://medium.com/@thepracticaldeveloper/top-open-source-llm-observability-tools-in-2025-d2d5cbf4b932)
- [McNemar's Test (MLM)](https://machinelearningmastery.com/mcnemars-test-for-machine-learning/)
- [Paired Bootstrap for NLP](https://medium.com/ai-enthusiast/comparing-nlp-models-with-confidence-the-paired-bootstrap-test-explained-c9a88532ea3d)
- [Statistical Significance Tests](https://machinelearningmastery.com/statistical-significance-tests-for-comparing-machine-learning-algorithms/)
- [streamlit-ace](https://github.com/okld/streamlit-ace) · [streamlit-ace PyPI](https://pypi.org/project/streamlit-ace/)
- [streamlit-code-editor](https://github.com/bouzidanas/streamlit-code-editor)
- [Build SQL Editor with Streamlit](https://viv1kv.medium.com/build-sql-editor-web-app-using-streamlit-and-sqlite-6a838169b791)
- [Gradio vs Streamlit](https://evidence.dev/learn/gradio-vs-streamlit)
- [CodeQL on Gradio (GitHub Blog)](https://github.blog/security/vulnerability-research/codeql-zero-to-hero-part-4-gradio-framework-case-study/)
- [Streamlit file_uploader CVE](https://www.catonetworks.com/blog/cato-ctrl-new-streamlit-vulnerability/)
- [LangGraph Persistence](https://docs.langchain.com/oss/javascript/langgraph/persistence)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [Trace LangGraph — Langfuse](https://langfuse.com/guides/cookbook/example_langgraph_agents)
- [LangChain vs LangFuse vs LangGraph vs LangSmith](https://amirteymoori.com/langchain-vs-langfuse-vs-langgraph-vs-langsmith-which-ai-tool-do-you-need/)
- [LangGraph State Management 2026](https://eastondev.com/blog/en/posts/ai/20260424-langgraph-agent-architecture/)
