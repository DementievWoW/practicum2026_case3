# When Prompts Become Payloads

- **Status:** NOT FOUND (вероятная галлюцинация в исходном списке)
- **Тип:** —
- **Канонический URL:** —
- **Год / venue:** не подтверждено

## Что это
Запрошенная "статья про прямые SQLi через манипуляцию промптом в LLM" с точным названием **"When Prompts Become Payloads"** не была найдена ни одним из следующих способов:

1. WebSearch с точной фразой в кавычках `"When Prompts Become Payloads"` — нет совпадений ни на arxiv, ни на ACM, ни на IEEE, ни на ACL Anthology, ни на security-блогах.
2. WebSearch с расширением `"When Prompts Become Payloads" SQL injection LLM`, `"When Prompts Become Payloads" 2024 2025 paper` — нулевые точные совпадения; возвращаются только перефразирующие материалы (Snyk, Cisco, Forcepoint, Medium-посты), без обнаружения работы с таким названием.
3. WebSearch `"prompts become payloads" LLM SQL injection` — также 0 совпадений как точного названия.

**Заключение:** название, скорее всего, является галлюцинацией модели. Возможно, идея перепутана с одной из реальных работ или популярных blog-постов (см. ниже), но статьи именно с этим заголовком в открытых индексах нет на 2026-05-18.

## Возможные реальные источники, которые могли быть перепутаны
- **From Prompt Injections to SQL Injection Attacks: How Protected is Your LLM-Integrated Web Application?** — arXiv: https://arxiv.org/abs/2308.01990 (Pedro et al., 2023). Описывает P2SQL атаки, эксплуатирующие LangChain-приложения.
- **Snyk blog: "LLM Weaponized via Prompt Injection to Generate SQL Injection Payloads"** — https://snyk.io/articles/llm-weaponized-via-prompt-injection-to-generate-sql-injection-payloads/
- **Cisco Blogs: "Prompt injection is the new SQL injection, and guardrails aren't enough"** — https://blogs.cisco.com/ai/prompt-injection-is-the-new-sql-injection-and-guardrails-arent-enough
- **Medium: "Prompt Injection Is the New SQL Injection"** — https://mayank1513.medium.com/prompt-injection-is-the-new-sql-injection-388ea936aaf0
- **Are Your LLM-based Text-to-SQL Models Secure? Exploring SQL Injection via Backdoor Attacks** — arXiv: https://arxiv.org/abs/2503.05445

## Почему релевантно (для аудита SQL)
Сама тематика — "промпт как payload" / P2SQL — критична для проекта аудита, но конкретное name-source необходимо подтвердить пользователем. До подтверждения **не цитировать в финальных артефактах под этим названием.**

## Верификация
- WebSearch 2026-05-18 × 3 запроса с точной фразой в кавычках → 0 совпадений
- Все возвращаемые результаты — описания концепции у независимых авторов, без статьи с указанным заголовком

## Рекомендация
Уточнить у источника правильное название. Если имелась в виду одна из реальных работ выше (особенно arXiv 2308.01990 — P2SQL), создать отдельную папку и перенести материал туда. На текущий момент данную запись считать **галлюцинацией** до получения дополнительных данных.

## Источник
- WebSearch: 2026-05-18 (`"When Prompts Become Payloads"`, `"When Prompts Become Payloads" SQL injection LLM`, `"prompts become payloads" LLM SQL injection attack natural language`)
- Подтверждено отсутствие индексации в открытых search engines
