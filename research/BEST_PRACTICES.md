# Лучшие практики — дистилляция research (круги 1–5)

> Сводка применимых практик из [`research/materials/`](materials/) (52 карточки,
> круги 1–5) и сводок [`research/00–05`](00_summary.md). Каждая практика —
> в повелительном наклонении, со ссылкой на карточку-источник и ключевым числом.
> Практики круга 6 (ансамбли/voting/boosting) — отдельно в
> [`research/06`](06_ensemble_gen_judge.md) и [`materials_round6/`](materials_round6/).
>
> Колонка «у нас» = где это уже зафиксировано в [ADR](../docs/adr/).

## TL;DR — что внедряем в первую очередь

1. **Гибрид, а не голый LLM-судья.** Детерминированный AST-слой (pglast) ловит
   структурные классы, LLM — триаж поверх находок + RAG. Голый LLM-as-judge на
   SQL ненадёжен (100% evasion линтеров у ToxicSQL). → ADR-0004.
2. **Schema linking — узкое место на 60 таблицах.** Soft-linking + summaries +
   FK-замыкание, иначе генератор плывёт. → ADR-0003.
3. **Multi-path генерация + выбор кандидата** (CHASE-SQL): несколько стратегий →
   pairwise-выбор «наименее уязвимого», не «самого точного».
4. **CWE/CAPEC-ID в каждом вердикте судьи** — иначе теряем баллы за прозрачность.
   → ADR-0005.
5. **Метрика EX — execution-based, multiset + permutation-aware**, а не exact
   match; для AST-эквивалентности смотреть ETM. → ADR-0007.
6. **`EXPLAIN` без `ANALYZE`** для тяжести: `ANALYZE` реально исполняет DML.

---

## 0. Архитектура цикла и оркестрация

| Практика | Источник | Ключевое | у нас |
|---|---|---|---|
| Цикл `Selector → Decomposer → Refiner`, execution-feedback заменить на **security-feedback** | [01/mag-sql](materials/01-generators-multiagent/mag-sql/), MAC-SQL (круг 1) | +14.7 пп к baseline на BIRD | ADR-0002 |
| Модульный 4-компонентный пайплайн: Schema Linking → Candidate Gen → Revision → Merge (кэшируется, легко заменить судью) | [08/base-sql](materials/08-production-cases/base-sql/) | BIRD 67.47%, ~5 LLM-вызовов/SQL | ADR-0002 |
| Явно разделять generative (генератор) и discriminative (судья) компоненты | [08/base-sql](materials/08-production-cases/base-sql/), Promethium | 70% прод-пилотов фейлятся без этого | ADR-0002 |
| LangGraph + `PostgresSaver` checkpoints + Langfuse-трейсы для A/B | круг 5, [00_summary](00_summary.md) | — | ADR-0002, 0009 |

## 1. Schema linking (ADR-0003)

| Практика | Источник | Ключевое |
|---|---|---|
| **Soft schema linking**: entity-based отбор колонок + human-readable summary таблицы для семантического матчинга с вопросом | [01/mag-sql](materials/01-generators-multiagent/mag-sql/) | 61.08% vs 46.35% baseline GPT-4 |
| **Vector-RAG по схеме**: метаданные → эмбеддинги → similarity-search, в промпт только релевантные куски (снижает шум на больших БД) | [11/aws-bedrock-rag-text2sql](materials/11-rag-techniques/aws-bedrock-rag-text2sql/) | — |
| top-15 таблиц + замыкание по FK (e5-multilingual + FAISS) | круг 2, [00_summary](00_summary.md) | 60 таблиц — узкое место |
| Robustness к возмущениям схемы (переименование колонок, синонимы, лишние таблицы) | [05/adveta-benchmark](materials/05-security-benchmarks-datasets/adveta-benchmark/) | SOTA теряет 14% (до 50.7%) |

## 2. Генератор кандидатов (ADR-0003)

| Практика | Источник | Ключевое |
|---|---|---|
| **Multi-path генерация**: divide-and-conquer + reasoning по execution-plan + synthetic examples — разные пути дают разные ошибки | [01/chase-sql](materials/01-generators-multiagent/chase-sql/) | BIRD 73.01% |
| **Targets-Conditions декомпозиция**: SELECT-поля и WHERE/JOIN/GROUP генерить раздельно, потом собирать | [01/mag-sql](materials/01-generators-multiagent/mag-sql/) | снижает hallucination |
| **Multi-sample**: 3–5 кандидатов (разные seed/prompt) → все на судью | [02/msc-sql](materials/02-critics-self-correction/msc-sql/) | Pass@K до 2× |
| **Plan → Test → Propose**: атомарные тест-зонды к БД, проверить логику, синтез финального SQL | [01/pexa](materials/01-generators-multiagent/pexa/) | 70.2% Spider 2.0 Snow |
| **Calibration hints**: каталог типовых ошибок (битые JOIN, агрегаты, привилегии) в system-prompt — «избегай этого» | [01/sqlfuse](materials/01-generators-multiagent/sqlfuse/) | для нас → каталог OWASP-паттернов |
| **Query-log few-shot**: офлайн (NL, SQL)-пары, выровненные по схеме; на runtime — few-shot для разрешения неоднозначностей | [09/soma-sql](materials/09-benchmarks-and-metrics/soma-sql/) | сильный baseline без frontier-моделей |
| DAIL-SQL Code-Representation + few-shot по similarity + self-consistency ×3–5 | круг 2, [00_summary](00_summary.md) | обязательный минимум промпта |

## 3. Выбор кандидата / ранкинг

| Практика | Источник | Ключевое |
|---|---|---|
| **Pairwise selection** (preference-based) вместо абсолютной оценки; для нас — критерий «least vulnerable» | [01/chase-sql](materials/01-generators-multiagent/chase-sql/) | снижает subjective bias |
| **Dual-paradigm consistency**: параллельная Python/Pandas-реализация + Minimal Distinguishing Database, сравнить результаты | [02/dpc-dual-paradigm-consistency](materials/02-critics-self-correction/dpc-dual-paradigm-consistency/) | +2.2 пп absolute |
| **Multi-sample critique**: маленькая модель-критик + метаданные (schema, exec-results, error-logs) оценивает N кандидатов | [02/msc-sql](materials/02-critics-self-correction/msc-sql/) | работает на Mistral/Gemma/Llama3 |

## 4. Self-correction / retry (ADR-0002 reflector)

| Практика | Источник | Ключевое |
|---|---|---|
| **Clause-wise critique**: оценивать SQL пощёлочно (SELECT/WHERE/JOIN/GROUP/HAVING), локализуя ошибку — интерпретируемо | [02/sqlcritic](materials/02-critics-self-correction/sqlcritic/) | SQLCriticBench |
| **3-stage Generate → Detect → Correct**: 70% ошибок в schema-linking и joins → таргетированная правка | [02/scot2s](materials/02-critics-self-correction/scot2s/) | +2.8% EM, +4.0% EX |
| **Review-Rebuttal-Revision**: агент предлагает → другие рецензируют → автор отвечает → итерации до консенсуса | [02/r3-review-rebuttal-revision](materials/02-critics-self-correction/r3-review-rebuttal-revision/) | Llama3-8B +20 пп vs CoT |
| **Error-token modeling**: execution-failures → спец-токены в семантич. пространстве (LLM игнорирует текстовые ошибки) | [02/errorllm](materials/02-critics-self-correction/errorllm/) | структурированный error-guided refinement |
| Reflexion memory-of-mistakes как состояние между итерациями | круг 1, [00_summary](00_summary.md) | +11% code (Reflexion) |

> ⚠️ `retrysql`, error-token-обучение и т.п. требуют **fine-tuning** (часто
> full-parameter, не LoRA) — у нас prompt-only (ADR-0003). Брать как идею
> промпта/состояния, не как обучение.

## 5. Детерминированный аудит (ADR-0004) — baseline судьи

| Практика | Источник | Ключевое |
|---|---|---|
| **libpg_query (нативный парсер PostgreSQL) + правила по AST, без подключения к БД** — анализ SQL-файлов в CI | [07/diesel-guard](materials/07-deterministic-tools/diesel-guard/) | 24 правила, AST через Rhai |
| Набор правил: DELETE/UPDATE без WHERE, `SELECT *`, отсутствие LIMIT, leading-wildcard LIKE, расхождение ORM↔миграции | [07/valk-guard](materials/07-deterministic-tools/valk-guard/) | 19 правил, PG-only, вывод SARIF/JSON |
| **`EXPLAIN (FORMAT JSON)` без ANALYZE** для тяжести плана | круг 3, [00_summary](00_summary.md) | ANALYZE исполняет DML! |
| Линтер сам — attack surface: контролируй конфиг (`library_path`, Jinja-macros) | [07/sqlfluff-cve-pre-2-1-2](materials/07-deterministic-tools/sqlfluff-cve-pre-2-1-2/) | CVE-2023-36830 |

**Что детерминированный слой ловит лучше LLM:** управляющие символы (CR/LF) и
meta-команды в идентификаторах; отсутствие WHERE/LIMIT; кодировко-зависимые
escape-баги; структурные антипаттерны. **Что добавляет LLM:** reasoning над
контекстом, адаптивность к новым угрозам, граничные случаи, провенанс.

## 6. LLM-судья + RAG (ADR-0005)

| Практика | Источник | Ключевое |
|---|---|---|
| **Experiential memory**: из логов прошлых разборов извлекать (scenario/risk/behavior) + CoT-трейсы, и multi-stage RAG подтягивает релевантные примеры рассуждений | [03/agentauditor](materials/03-rag-judges/agentauditor/) | 2293 records, 15 рисков, 29 сценариев |
| **Provenance-driven critique**: self-critique с cross-reference к верифицируемым источникам (CWE/NVD/PG-advisories), фиксировать провенанс факта | [03/proverag](materials/03-rag-judges/proverag/) | 99% exploit / 97% mitigation; +30% при chunking |
| **Agentic роли** Explorer → RAG → Analyst → Reporter + мультиметричный judge (4 оси качества отчёта) | [03/raven-rag-vulnerability](materials/03-rag-judges/raven-rag-vulnerability/) | 105 samples, 15 CWE |
| CWE/CAPEC/ASVS-ID обязательны в выводе; если чанк не подтянут — `evidence:{}` + `unverified` | круг 4, [00_summary](00_summary.md) | «прозрачность» = 10 баллов |
| Payloads — только negative-test corpus, **не** в runtime-контекст судьи | круг 4 | иначе судья «учится» опасному SQL |

## 7. Устойчивость судьи к атакам

| Практика | Источник | Ключевое |
|---|---|---|
| Прогонять судью через suite атак (AutoDAN, PAIR, combined, jailbreak) + 7 защит (re-tokenization, detectors, temp↓, masking, prompt-diversity); мерить SDR/ASR | [03/robustjudge](materials/03-rag-judges/robustjudge/) | robustness гуляет до 40% от шаблона |
| 4 защиты от P2SQL: валидация+параметризация, ограничение ролей/привилегий, SQL-sandbox (только SELECT), content-filter | [04/p2sql-injection-langchain](materials/04-security-attacks/p2sql-injection-langchain/) | 7 LLM, 5 реальных приложений |
| Маскировать schema-информацию в ошибках/выводе — защита от schema-inference | [04/schema-inference-attack](materials/04-security-attacks/schema-inference-attack/) | атака даёт F1≈0.99 |
| Тест-suite замаскированных SQLi (GAN-мутации, сохраняющие семантику) — проверка, ловит ли судья | [04/gsqli-gan-waf-bypass](materials/04-security-attacks/gsqli-gan-waf-bypass/) | WAF-bypass payloads |
| Мелкозернистые tools с привязкой к привилегиям БД; proxy для передачи данных в обход LLM-канала | [04/bridgescope](materials/04-security-attacks/bridgescope/) | −80% токенов |

## 8. PostgreSQL-специфика (CVE 2025 + ADR-0010)

| Практика | Источник | CVSS |
|---|---|---|
| Не доверять `PQescape*()` как полной защите при многобайтовых кодировках — требовать параметризацию | [06/cve-2025-1094-libpq-escaping](materials/06-postgres-cves/cve-2025-1094-libpq-escaping/) | 8.1 |
| Парсить идентификаторы на CR/LF и psql meta (`\!`) — блокировать newlines в именах объектов | [06/cve-2025-8715-psql-meta](materials/06-postgres-cves/cve-2025-8715-psql-meta/) | 8.8 (CWE-93) |
| dump/restore из untrusted-источника — high-risk, требовать ревью | [06/cve-2025-8714-pg-dump-injection](materials/06-postgres-cves/cve-2025-8714-pg-dump-injection/) | 8.8 (CWE-829) |
| `SECURITY DEFINER` без `SET search_path` и `EXECUTE` с `\|\|` — детект-правила; PL/pgSQL через `plpgsql_check` | круг 3/5, [00_summary](00_summary.md) | бонус +10 |

## 9. Синтез датасета (ADR-0006)

| Практика | Источник | Ключевое |
|---|---|---|
| **SQL-to-Text back-translation** (проще, чем Text-to-SQL): берём SQL → LLM пишет NL | круг 5, [00_summary](00_summary.md) | OmniSQL/SynSQL |
| Шаблонный multi-perspective синтез поверх реальной схемы (вкл. insider-кейсы) | [05/superviz25-sql](materials/05-security-benchmarks-datasets/superviz25-sql/) | 62 шаблона → 3.3M |
| Пейлоады из **нескольких** источников (PayloadsAllTheThings + LLM + ручные) — снижает bias | [05/rbsqli-10m](materials/05-security-benchmarks-datasets/rbsqli-10m/) | 6 категорий SQLi |
| Размечать как (NL, SQL, vuln_class, technique); таксономия по CWE-89 / OWASP-LLM-Top-10 | [05/nist-sard](materials/05-security-benchmarks-datasets/nist-sard/), [10/peerj-survey](materials/10-surveys-and-reviews/peerj-llm-text2sql-security-survey/) | 150+ CWE классов |
| Добавлять **insider-attack** примеры (синтаксически валидные, тянут защищённые данные) для оценки FP | [05/superviz25-sql](materials/05-security-benchmarks-datasets/superviz25-sql/) | 1089 примеров |

> ⚠️ **Антипаттерн:** чисто rule-based разметка 10M даёт label noise
> ([05/rbsqli-10m](materials/05-security-benchmarks-datasets/rbsqli-10m/)) — у нас
> quality-gate «Phase 1 подтверждает класс» + спот-чек (ADR-0006).

## 10. Метрики и оценка (ADR-0007)

| Практика | Источник | Ключевое |
|---|---|---|
| **ETM (Enhanced Tree Matching)** — AST + verifiable equivalence, вместо exact match / голого execution | [09/etm-enhanced-tree-matching](materials/09-benchmarks-and-metrics/etm-enhanced-tree-matching/) | FP/FN 0.3%/2.7% vs 23%/28.9% |
| EX: execution-based, **multiset + permutation-aware** (unordered rows, column-order, дубликаты) | [11/ibm-querycraft](materials/11-rag-techniques/ibm-querycraft/) | + timeout 30с |
| Per-module метрики (Schema Selection / Candidate Gen / Revision) — честное сравнение при замене одного узла | [09/nl2sqlbench](materials/09-benchmarks-and-metrics/nl2sqlbench/) | 3 модуля |
| Security-метрики per-attack (P/R/F1 по классам + coverage), а не общий accuracy | [05/securesql-benchmark](materials/05-security-benchmarks-datasets/securesql-benchmark/) | 4 типа атак, 932 примера |
| Калибровать ожидания на сложных многотабличных БД (бизнес-домен, ~26 таблиц) | [09/corgi-benchmark](materials/09-benchmarks-and-metrics/corgi-benchmark/) | −33% accuracy vs BIRD |
| McNemar p-value на eval-set для значимости A/B | круг 5, [00_summary](00_summary.md) | дешёвое «вино» на защите |

## 11. Антипаттерны и подводные камни

- **LLM-as-judge на голом SQL ненадёжен** (ToxicSQL, 100% evasion линтеров) → только гибрид AST+RAG. (круг 1/3)
- **`EXPLAIN ANALYZE` исполняет** UPDATE/DELETE/INSERT → только `EXPLAIN` без ANALYZE либо `BEGIN; … ROLLBACK;`. (круг 3)
- **Линтер — тоже attack surface** (SQLFluff Jinja RCE). (07/sqlfluff)
- **Gap академия↔прод**: бенчмарки 80%+, прод 10–20% на сложных вопросах, 70% пилотов не доходят до прода — это и оправдывает судью. ([10/promethium](materials/10-surveys-and-reviews/promethium-state-of-text2sql-2025/))
- **Игнорировать выводы недостоверных карточек:** `dorysql-amazon` (вероятная галлюцинация), `when-prompts-become-payloads` (не найдено); число SOMA-SQL 72.02% публично не подтверждено. (см. [materials/README](materials/README.md))

---

## Источники
- Карточки: [`research/materials/`](materials/) (круги 1–5).
- Сводки кругов: [00](00_summary.md) · [01](01_multiagent_text2sql.md) · [02](02_text2sql_benchmarks.md) · [03](03_deterministic_validators.md) · [04](04_rag_knowledge_base.md) · [05](05_peripheral.md).
- Решения: [`docs/adr/`](../docs/adr/) (ADR-0002…0010).
