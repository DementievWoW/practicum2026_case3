# AgentAuditor: Human-Level Safety and Security Evaluation for LLM Agents

- **Status:** verified
- **Тип:** paper (arXiv preprint + OpenReview)
- **Канонический URL:** https://arxiv.org/abs/2506.00641
- **PDF:** https://arxiv.org/pdf/2506.00641
- **OpenReview:** https://openreview.net/forum?id=2KKqp7MWJM
- **Год / venue:** 2025-05-31 (v1), последняя ревизия 2026-01-31; OpenReview submission
- **Авторы:** Hanjun Luo, Shenyu Dai, Chiming Ni, Xinfeng Li, Guibin Zhang, Kun Wang, Tongliang Liu, Hanan Salam

## Что это
AgentAuditor — universal, training-free, memory-augmented reasoning фреймворк, который превращает LLM-evaluator в "human-expert-level" судью безопасности LLM-агентов. Метод: LLM адаптивно извлекает структурированные семантические признаки (scenario, risk, behavior) из прошлых interaction-логов и генерирует chain-of-thought reasoning traces — формируя experiential memory. Затем multi-stage, context-aware RAG-процесс динамически извлекает наиболее релевантные reasoning-эксперименты для оценки нового case. Параллельно представлен ASSEBench — first benchmark для evaluation safety и security одновременно: 2293 размеченных interaction records, 15 risk types, 29 application scenarios; вводит "Strict" и "Lenient" judgment standards для разрешения ambiguous risk situations. Заявлено: state-of-the-art LLM-as-a-judge для agent safety/security, достигает human-level accuracy.

## Почему релевантно
Полная методология RAG-augmented LLM-judge для оценки безопасности агентов — целевой паттерн для аудита SQL-агентов. Структурированные семантические признаки (scenario/risk/behavior) и память над reasoning traces переносятся 1:1 на PostgreSQL: хранить судебные решения по прошлым SQLi-кейсам как опыт. Strict/Lenient двойной стандарт полезен для разрешения граничных уязвимостей.

## Цитаты (verbatim из abstract)
- "AgentAuditor constructs an experiential memory by having an LLM adaptively extract structured semantic features (e.g., scenario, risk, behavior) and generate associated chain-of-thought reasoning traces for past interactions."
- "A multi-stage, context-aware retrieval-augmented generation process then dynamically retrieves the most relevant reasoning experiences to guide the LLM evaluator's assessment of new cases."
- "ASSEBench comprises 2293 meticulously annotated interaction records, covering 15 risk types across 29 application scenarios."

## Верификация
- WebFetch https://arxiv.org/abs/2506.00641 → подтверждены title, авторы, abstract, ASSEBench
- OpenReview pdf confirms paper существует с тем же названием и idea
- ResearchGate publication 392334846 — independent index

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2506.00641
- Дополнительно: https://openreview.net/forum?id=2KKqp7MWJM
