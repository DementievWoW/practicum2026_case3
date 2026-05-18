# Materials — верифицированные материалы по проекту

Каждая папка — одна работа (paper / github / blog / benchmark / CVE / tool). Внутри `README.md` со статусом верификации (`verified` / `verified (corrected URL)` / `NOT FOUND`), каноническим URL, кратким описанием и (для репозиториев) превью реального README с GitHub.

**Сводно:** проверено 52 материала. **49 verified**, **3 NOT FOUND** (один — GitHub-репо к реальной статье; два — материалы, не существующие в открытых источниках, помечены как «вероятно, галлюцинация»).

В исходных списках было **~10 URL, ведущих не туда** (чужие статьи по физике, лемматизаторам, FPGA-тестам) или placeholder-ID (`cs-12345`, `2503.12345`, `250612345B`). Все скорректированы или помечены как `NOT FOUND`.

## Карта групп

| # | Группа | Кол-во | Что внутри |
|---|---|---|---|
| 01 | [generators-multiagent/](01-generators-multiagent/) | 6 | Мультиагентные T2SQL фреймворки (генератор + критик/судья) |
| 02 | [critics-self-correction/](02-critics-self-correction/) | 8 | Паттерны критика, self-correction, retry, refinement |
| 03 | [rag-judges/](03-rag-judges/) | 4 | RAG-фреймворки и LLM-судьи для оценки уязвимостей и agent safety |
| 04 | [security-attacks/](04-security-attacks/) | 5 | Атаки на T2SQL и SQLi через LLM (P2SQL, schema-inference, WAF-bypass) |
| 05 | [security-benchmarks-datasets/](05-security-benchmarks-datasets/) | 6 | Датасеты и бенчмарки для тренировки/тестирования судьи |
| 06 | [postgres-cves/](06-postgres-cves/) | 3 | PostgreSQL CVE 2025 (libpq, pg_dump, psql) |
| 07 | [deterministic-tools/](07-deterministic-tools/) | 3 | Линтеры и SAST: Valk Guard, Diesel Guard, SQLFluff CVE |
| 08 | [production-cases/](08-production-cases/) | 6 | Продакшен-системы и open-source frameworks (PremSQL, BASE-SQL, ADEPT-SQL, ...) |
| 09 | [benchmarks-and-metrics/](09-benchmarks-and-metrics/) | 6 | Бенчмарки T2SQL и новые метрики (ETM/ESM+, CORGI, NL2SQLBench) |
| 10 | [surveys-and-reviews/](10-surveys-and-reviews/) | 3 | Обзоры по T2SQL и индустрии |
| 11 | [rag-techniques/](11-rag-techniques/) | 2 | RAG-туториалы по T2SQL (AWS Bedrock, IBM QueryCraft) |

## Детальный индекс

### 01 — generators-multiagent (6)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [bappa](01-generators-multiagent/bappa/) | paper + repo | verified | https://arxiv.org/abs/2511.04153 |
| [chase-sql](01-generators-multiagent/chase-sql/) | paper | verified | https://arxiv.org/abs/2410.01943 |
| [mag-sql](01-generators-multiagent/mag-sql/) | paper + repo | verified (corrected URL) | https://arxiv.org/abs/2408.07930 |
| [magesql](01-generators-multiagent/magesql/) | paper | verified (corrected description: не spatial) | CIKM 2024 demo |
| [pexa](01-generators-multiagent/pexa/) | blog | verified | Bloomberg AI |
| [sqlfuse](01-generators-multiagent/sqlfuse/) | paper | verified (corrected URL: `2407.17568` → `2407.14568`) | https://arxiv.org/abs/2407.14568 |

### 02 — critics-self-correction (8)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [actor-critic-text2sql](02-critics-self-correction/actor-critic-text2sql/) | paper | verified (corrected URL: `2410.18543` → `2410.22082`) | https://arxiv.org/abs/2410.22082 |
| [dpc-dual-paradigm-consistency](02-critics-self-correction/dpc-dual-paradigm-consistency/) | paper + repo | verified (corrected URL: `2604.11233` → `2604.15163`) | https://arxiv.org/abs/2604.15163 |
| [errorllm](02-critics-self-correction/errorllm/) | paper | verified (год — 2026, не 2026 «весна») | https://arxiv.org/abs/2603.03742 |
| [msc-sql](02-critics-self-correction/msc-sql/) | paper + repo | verified (corrected URL: `naacl-long.122` → `naacl-long.107`) | https://arxiv.org/abs/2410.12916 |
| [r3-review-rebuttal-revision](02-critics-self-correction/r3-review-rebuttal-revision/) | paper, repo NOT FOUND | partially verified | https://aclanthology.org/2025.trl-1.4/ (GitHub `1ring2rta/R3` → 404) |
| [retrysql](02-critics-self-correction/retrysql/) | paper | verified | https://arxiv.org/abs/2507.02529 |
| [scot2s](02-critics-self-correction/scot2s/) | paper | verified (год — 2025, не 2026) | ScienceDirect S0885230825000907 |
| [sqlcritic](02-critics-self-correction/sqlcritic/) | paper | verified (corrected URL: placeholder `2503.12345` → `2503.07996`) | https://arxiv.org/abs/2503.07996 |

### 03 — rag-judges (4)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [agentauditor](03-rag-judges/agentauditor/) | paper | verified | https://arxiv.org/abs/2506.00641 |
| [proverag](03-rag-judges/proverag/) | paper | verified | https://arxiv.org/abs/2410.17406 |
| [raven-rag-vulnerability](03-rag-judges/raven-rag-vulnerability/) | paper | verified | https://arxiv.org/abs/2604.17948 |
| [robustjudge](03-rag-judges/robustjudge/) | paper + repo | verified | https://arxiv.org/abs/2506.09443 |

### 04 — security-attacks (5)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [bridgescope](04-security-attacks/bridgescope/) | paper | verified (corrected URL: ADS placeholder → `2508.04031`) | https://arxiv.org/abs/2508.04031 |
| [gsqli-gan-waf-bypass](04-security-attacks/gsqli-gan-waf-bypass/) | paper | verified | IEEE ICCAI 2025, document/11106089 |
| [p2sql-injection-langchain](04-security-attacks/p2sql-injection-langchain/) | paper | verified | https://arxiv.org/abs/2308.01990 |
| [schema-inference-attack](04-security-attacks/schema-inference-attack/) | paper | **verified (corrected URL: `2506.03556` ведёт на чужую FPGA-статью → правильный `2406.14545`)** | https://arxiv.org/abs/2406.14545 |
| [when-prompts-become-payloads](04-security-attacks/when-prompts-become-payloads/) | **NOT FOUND** | вероятно, галлюцинация | — |

### 05 — security-benchmarks-datasets (6)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [adveta-benchmark](05-security-benchmarks-datasets/adveta-benchmark/) | benchmark | verified | https://arxiv.org/abs/2212.09994 |
| [nist-sard](05-security-benchmarks-datasets/nist-sard/) | dataset | verified | https://samate.nist.gov/SARD/ |
| [rbsqli-10m](05-security-benchmarks-datasets/rbsqli-10m/) | dataset | verified | Mendeley Data v3 |
| [securesql-benchmark](05-security-benchmarks-datasets/securesql-benchmark/) | benchmark | verified | https://aclanthology.org/2024.findings-emnlp.346/ |
| [sqlqueryshield](05-security-benchmarks-datasets/sqlqueryshield/) | model + dataset | verified | https://huggingface.co/salmane11/SQLQueryShield |
| [superviz25-sql](05-security-benchmarks-datasets/superviz25-sql/) | dataset | verified | https://zenodo.org/records/17086037 |

### 06 — postgres-cves (3)

| CVE | Где | CVSS | Канонический URL |
|---|---|---|---|
| [CVE-2025-1094 (libpq escaping)](06-postgres-cves/cve-2025-1094-libpq-escaping/) | libpq escape + BIG5/EUC_TW | 8.1 HIGH | https://nvd.nist.gov/vuln/detail/CVE-2025-1094 |
| [CVE-2025-8714 (pg_dump injection)](06-postgres-cves/cve-2025-8714-pg-dump-injection/) | pg_dump → CWE-829 | 8.8 HIGH | https://nvd.nist.gov/vuln/detail/CVE-2025-8714 |
| [CVE-2025-8715 (psql meta-command)](06-postgres-cves/cve-2025-8715-psql-meta/) | newline → psql meta, CWE-93 | 8.8 HIGH | https://nvd.nist.gov/vuln/detail/CVE-2025-8715 |

### 07 — deterministic-tools (3)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [diesel-guard](07-deterministic-tools/diesel-guard/) | github (Rust) | verified | https://github.com/ayarotsky/diesel-guard |
| [sqlfluff-cve-pre-2-1-2](07-deterministic-tools/sqlfluff-cve-pre-2-1-2/) | CVE | verified | CVE-2023-36830 / GHSA-jqhc-m2j3-fjrx |
| [valk-guard](07-deterministic-tools/valk-guard/) | github | verified | https://github.com/ValkDB/valk-guard |

### 08 — production-cases (6)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [adept-sql](08-production-cases/adept-sql/) | paper (ACL 2025 Demo) | verified | https://aclanthology.org/2025.acl-demo.27/ |
| [base-sql](08-production-cases/base-sql/) | github | verified | https://github.com/CycloneBoy/base_sql |
| [oracle-mysql-nl2sql](08-production-cases/oracle-mysql-nl2sql/) | blog | verified (403 fallback) | blogs.oracle.com |
| [premsql](08-production-cases/premsql/) | github + PyPI | verified | https://github.com/premAI-io/premsql |
| [querymind](08-production-cases/querymind/) | github | verified | https://github.com/Tangxihong0922/QueryMind |
| [text2sql-skill](08-production-cases/text2sql-skill/) | github (Go) | verified | https://github.com/ljq/text2sql-skill |

### 09 — benchmarks-and-metrics (6)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [corgi-benchmark](09-benchmarks-and-metrics/corgi-benchmark/) | benchmark | verified (год: 2025, не 2026) | https://arxiv.org/abs/2510.07309 |
| [dorysql-amazon](09-benchmarks-and-metrics/dorysql-amazon/) | **NOT FOUND** | **вероятно, галлюцинация** (Amazon не публиковал такую модель) | — |
| [esm-plus](09-benchmarks-and-metrics/esm-plus/) | metric | verified (в v3 переименован в ETM) | https://arxiv.org/abs/2407.07313 |
| [etm-enhanced-tree-matching](09-benchmarks-and-metrics/etm-enhanced-tree-matching/) | metric | verified | https://arxiv.org/abs/2407.07313 |
| [nl2sqlbench](09-benchmarks-and-metrics/nl2sqlbench/) | benchmark | verified | https://arxiv.org/abs/2604.16493 (PVLDB Vol.19) |
| [soma-sql](09-benchmarks-and-metrics/soma-sql/) | blog | verified (число 72.02% не подтверждено публичным фрагментом) | blogs.oracle.com |

### 10 — surveys-and-reviews (3)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [peerj-llm-text2sql-security-survey](10-surveys-and-reviews/peerj-llm-text2sql-security-survey/) | survey | verified (corrected URL: `cs-12345` placeholder → `cs-3773`) | https://peerj.com/articles/cs-3773/ |
| [promethium-state-of-text2sql-2025](10-surveys-and-reviews/promethium-state-of-text2sql-2025/) | industry report | verified | promethium.ai |
| [tkde-2025-text2sql-survey](10-surveys-and-reviews/tkde-2025-text2sql-survey/) | survey | verified | https://arxiv.org/abs/2408.05109 |

### 11 — rag-techniques (2)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [aws-bedrock-rag-text2sql](11-rag-techniques/aws-bedrock-rag-text2sql/) | blog | verified | aws.amazon.com/blogs/machine-learning |
| [ibm-querycraft](11-rag-techniques/ibm-querycraft/) | blog | verified | medium.com/towards-generative-ai |

## Ключевые ошибки в исходных списках (что было исправлено при верификации)

1. **`schema-inference-attack` (`arXiv:2506.03556`)** — ссылка из «свежей» подборки указывала на **чужую статью про FPGA-тесты**. Без верификации это бы попало в обзор как «ZK Schema Inference». Правильный URL: [2406.14545](https://arxiv.org/abs/2406.14545) (Klisura & Rios, NAACL 2025 Findings).
2. **`sqlfuse` (`arXiv:2407.17568`)** — ссылка вела на статью **по теоретической физике (gr-qc)**. Правильный ID — `2407.14568`.
3. **`actor-critic-text2sql` (`arXiv:2410.18543`)** — ссылка вела на статью **про сверхпроводящие кубиты**. Правильный ID — `2410.22082` (Zheng et al.).
4. **`dpc-dual-paradigm-consistency` (`arXiv:2604.11233`)** — ссылка вела на статью **про лемматизатор RUMLEM**. Правильный ID — `2604.15163`.
5. **`sqlcritic` (`arXiv:2503.12345`)** — очевидный **placeholder-ID**. Найдено: `2503.07996`.
6. **`msc-sql` (`aclanthology.org/2025.naacl-long.122`)** — указывала на **чужую работу про social bias**. Правильно: `naacl-long.107`.
7. **`peerj-llm-text2sql-security-survey` (`cs-12345`)** — очевидный **placeholder**. Найдено: `cs-3773`.
8. **`bridgescope` (`2025arXiv250612345B`)** — placeholder в ADS-ID. Реальный arXiv: `2508.04031`.
9. **`magesql` — описание неверно**: исходно заявлено «для spatial SQL», на деле — general multi-agent demo CIKM 2024.
10. **`corgi-benchmark` и `scot2s` — год**: оба маркированы «2026», на деле **2025**.

## Materials с пометкой NOT FOUND / возможной галлюцинацией

| Материал | Что заявлено | Что нашлось при проверке |
|---|---|---|
| [r3-review-rebuttal-revision](02-critics-self-correction/r3-review-rebuttal-revision/) | paper + GitHub `1ring2rta/R3` | **Paper существует**, GitHub возвращает 404 |
| [dorysql-amazon](09-benchmarks-and-metrics/dorysql-amazon/) | «Amazon DorySQL 3B-MoE, 74.85% BIRD» | **Ни на arXiv, ни на Amazon Science, ни на BIRD leaderboard следов нет.** Вероятно, галлюцинация |
| [when-prompts-become-payloads](04-security-attacks/when-prompts-become-payloads/) | статья про прямые SQLi через манипуляцию промптом | **Точная фраза не находится в открытых источниках.** Реальные альтернативы (P2SQL/Snyk-блог) указаны в README |
