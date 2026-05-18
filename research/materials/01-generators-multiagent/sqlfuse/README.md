# SQLfuse: Enhancing Text-to-SQL Performance through Comprehensive LLM Synergy

- **Status:** verified (corrected URL — оригинальный arxiv.org/abs/2407.17568 ведёт на статью по теоретической физике, не на SQLfuse; правильный ID — 2407.14568)
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2407.14568
- **Альтернативный URL:** https://arxiv.org/html/2407.14568v1 ; https://dblp.org/rec/journals/corr/abs-2407-14568.html
- **Год / venue:** arXiv (cs.CL), submitted July 19, 2024

## Что это
SQLfuse — система компании Ant Group, объединяющая open-source LLM с пайплайном из четырёх модулей:
1. **Schema mining**
2. **Schema linking**
3. **SQL generation**
4. **SQL critic module** — на основе Llama2-70B; использует «calibration hints», перечисляющие частые ошибки, чтобы предотвратить их повторение.

Достигнуто лидирующее место на Spider Leaderboard; система задеплоена в Ant Group для реальных бизнес-задач.

Авторы: Tingkai Zhang, Chaoyu Chen, Cong Liao, Jun Wang, Xudong Zhao, Hang Yu, Jianchao Wang, Jianguo Li, Wenhui Shi.

## Почему релевантно нашему кейсу
**SQL Critic module** — это буквальная реализация роли «судьи» из GreenData кейса. Calibration hints (каталог типовых ошибок) переводятся напрямую в каталог security-паттернов (OWASP SQLi / privilege escalation / data exfiltration), которые судья сверяет с кандидатом.

## README-превью (только для GitHub репо)
Не применимо — в задании указан только arXiv preprint, публичный GitHub в выдаче не найден.

## Источник
- WebFetch'нуто: 2026-05-18
  - https://arxiv.org/abs/2407.17568 (НЕВЕРНЫЙ — ведёт на «Spatial curvature in coincident gauge f(Q) cosmology», Erik Jensko, gr-qc)
  - https://arxiv.org/abs/2407.14568 (корректный, успешно)
- Цитаты:
  - "SQLfuse features four integrated modules: schema mining, schema linking, SQL generation, and a SQL critic module" (arXiv abstract)
  - "continuously enhance SQL query quality" (arXiv abstract)
  - "leading performance on the Spider Leaderboard" и "deployment by Ant Group" (arXiv abstract)
  - "An open-source LLM Llama2-70B is mainly used as the SQL critic model" (WebSearch summary of arXiv)
