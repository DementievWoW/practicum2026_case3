# Круг 1 — Мультиагентные Text-to-SQL с этапом критика

Самый релевантный круг. Это «ядро» — прямые архитектурные прототипы цикла «генератор ↔ судья».

## Блок 1. Мультиагентные Text-to-SQL фреймворки

### 1. CHESS — Contextual Harnessing for Efficient SQL Synthesis (ICML 2025)
- arXiv: https://arxiv.org/abs/2405.16755
- Repo: https://github.com/ShayanTalaei/CHESS
- 4 агента: Information Retriever, Schema Selector, Candidate Generator (генерация + iterative refinement), Unit Tester (LLM-юнит-тесты на NL-уровне).
- 65–66 % execution accuracy на BIRD.
- **Польза**: референс-архитектура retriever → selector → generator → tester; pruning большой схемы.

### 2. MAC-SQL — Multi-Agent Collaborative Framework (COLING 2025) ⭐
- arXiv: https://arxiv.org/abs/2312.11242
- Repo: https://github.com/wbbeyourself/MAC-SQL
- Три агента: **Selector** (отрезает лишние таблицы), **Decomposer** (CoT-разбиение), **Refiner** (executes, ловит фидбек, чинит). Лимит 3 итерации.
- **Самый близкий прототип нашего случая.** Refiner = «судья». Промпт-шаблоны переиспользуются, нужно заменить execution-feedback на security-feedback.

### 3. DIN-SQL — Decomposed In-Context Learning with Self-Correction (NeurIPS 2023)
- arXiv: https://arxiv.org/abs/2304.11015
- 4 модуля: schema linking → query classification → SQL generation → self-correction.
- Два стиля self-correction: «generic» и «gentle» (для GPT-4 работает gentle).
- **Польза**: два готовых стиля промпта для критика. SOTA-прирост ~10 %.

### 4. MCS-SQL — Multiple-Choice Selection (COLING 2025)
- arXiv: https://arxiv.org/abs/2405.07467
- Генерит N кандидатов разными промптами, фильтрует по confidence, финальный SQL выбирает LLM из multiple-choice списка.
- 65.5 % BIRD / 89.6 % Spider.
- **Польза**: альтернатива итеративному циклу — параллельный sampling + judge-выбор.

### 5. DAIL-SQL — Prompt Engineering & Self-Consistency
- Repo: https://github.com/BeachWang/DAIL-SQL
- 5 представлений вопроса, 4 стратегии выбора примеров, execution-based self-consistency voting.
- 86.6 % Spider-test.
- **Польза**: «библия» по prompt-engineering для NL2SQL.

### 6. SQL-PaLM (Google, 2023)
- arXiv: https://arxiv.org/abs/2306.00739
- Few-shot + instruction tuning + execution-based self-consistency.
- **Польза**: ценность execution-feedback; идея «несколько кандидатов → судья выбирает».

## Блок 2. Reflexion / Self-Refine для SQL

### 7. Self-Refine (Madaan, 2023) + Reflexion (Shinn, NeurIPS 2023)
- Self-Refine: https://arxiv.org/abs/2303.17651 | https://selfrefine.info/
- Reflexion: https://openreview.net/pdf?id=vAElhFcKW6
- Self-Refine: одна LLM генерирует, та же даёт фидбек, та же исправляет, +20 % средне. Reflexion: «вербальный RL» — память о прошлых ошибках, +22 % decision / +11 % code.
- **Польза**: теоретическая база цикла. Memory-of-mistakes — судья пишет короткий «урок», который кладётся в контекст следующей итерации генератора.

### 8. ReFoRCE (Spider 2.0 SOTA, 2025) + PaVeRL-SQL (2025)
- ReFoRCE: https://arxiv.org/abs/2502.00675
- PaVeRL-SQL: https://arxiv.org/html/2509.07159
- ReFoRCE: self-refinement + format restriction + column exploration, до 3 итераций по execution feedback. PaVeRL-SQL: partial-match rewards + verbal RL.
- **Польза**: свежие 2025 SOTA с доказанным verbal-RL.

## Блок 3. LangGraph generator-critic туториалы

### 9. LangChain Reflection Agents + LangGraph SQL Agent ⭐
- Blog: https://blog.langchain.com/reflection-agents/
- Docs: https://docs.langchain.com/oss/python/langgraph/sql-agent
- Notebook: https://github.com/langchain-ai/langgraph/blob/main/examples/tutorials/sql-agent.ipynb
- IBM tutorial: https://www.ibm.com/think/tutorials/build-sql-agent-langgraph-mistral-medium-3-watsonx-ai
- Паттерн: два узла MessageGraph (`generator` ↔ `reflector`), фиксированный лимит итераций.
- **Польза**: код почти под копирку. ToolNode + tools_condition позволяет судье дёргать внешний линтер (sqlfluff, pglast) как tool.

## Блок 4. LLM SQL injection auditor / security review

### 10. ToxicSQL / «Are Your LLM-based Text-to-SQL Models Secure?» (SIGMOD/PACMMOD 2025) ⭐
- arXiv: https://arxiv.org/abs/2503.05445
- 0.44 % отравленных данных → 79.41 % успешных backdoor SQLi. Каталог триггеров атак.
- **Польза**: готовый список классов атак для судьи + ground-truth для оценки.

### Доп. находки по безопасности

- **SQL Injection in LLM-Generated Queries** (IEEE 2025): https://ieeexplore.ieee.org/document/11355472/
  - 100 % evasion rate для SQLFluff/SQLLint/SonarQube по adversarial-payloads → одного статического линтера мало.
- **LSAST**: https://arxiv.org/html/2409.15735v2 — LLM + SAST scanner интеграция.
- **QLPro**: https://arxiv.org/html/2506.23644v1 — triple-voting LLM-judges поверх static analysis.
- **Trend Micro LLM as a Judge**: https://www.trendmicro.com/vinfo/us/security/news/managed-detection-and-response/llm-as-a-judge-evaluating-accuracy-in-llm-security-scans
- **OWASP Top-10 for LLM Apps 2025**: https://www.lasso.security/blog/owasp-top-10-llm-vulnerabilities-security-checklist

## Блок 5. Продакшен-кейсы

### Uber QueryGPT
- https://www.uber.com/en-GB/blog/query-gpt/
- 4 агента: Workspaces, Intent, Table, Column Prune. 1.2M запросов/мес, время 10 мин → 3 мин.

### Pinterest Text-to-SQL
- https://medium.com/pinterest-engineering/how-we-built-text-to-sql-at-pinterest-30bad30dabff
- RAG-таблица-селектор; обработка low-cardinality values (`'web'` → `'WEB'`). +35 % к скорости.

### LinkedIn «Practical Text-to-SQL for Data Analytics»
- https://www.linkedin.com/blog/engineering/ai/practical-text-to-sql-for-data-analytics

## Топ-3 «обязательно изучить»

1. **MAC-SQL** — клонировать репо, понять промпты Refiner, заменить execution-feedback на security-feedback. Минимальная адаптация, максимальный буст.
2. **LangChain Reflection Agents + LangGraph SQL Agent** — инженерная база. Цикл generator↔reflector пишется в 50 строк.
3. **ToxicSQL + OWASP LLM Top-10** — таксономия 9 классов уязвимостей + adversarial-датасет.
