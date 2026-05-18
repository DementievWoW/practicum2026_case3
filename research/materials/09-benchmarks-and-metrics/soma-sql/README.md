# SOMA-SQL (Oracle, Spider 2.0 Lite)

- **Status:** verified (через WebSearch и emergentmind; основной Oracle-блог отдал HTTP 403, но публикация подтверждена несколькими источниками)
- **Тип:** blog (vendor announcement) + методический подход
- **Канонический URL:** https://blogs.oracle.com/cloud-infrastructure/oci-gen-ai-tops-spider-2-lite (403 при WebFetch — Oracle режет ботов)
- **Год / venue:** 2026 (по контексту «#1 on Spider 2.0 Lite»), Oracle Cloud Infrastructure / OCI Gen AI Blog

## Что это
Анонс Oracle: их система SOMA-SQL занимает #1 на лидерборде Spider 2.0 Lite (NL→SQL benchmark, 547 примеров, BigQuery/Snowflake/SQLite). Метод: оффлайн строит «ambiguity-aware query log» из пар (NL-вопрос, SQL-запрос), выровненных по схеме БД; на инференсе достаёт самые релевантные примеры как few-shot контекст для разрешения неоднозначностей. Конкретное число «72.02%» в публично доступных фрагментах источников **не зафиксировано** — оно фигурирует только в постановке задачи; в найденных фрагментах указаны только сопоставительные цифры (ReFoRCE 26.69%, Spider-Agent o1-preview 20.29%, DAIL-SQL GPT-4o 2.20%). Точная цифра требует доступа к оригинальному блогу.

## Почему релевантно
SOMA-SQL — показательный enterprise-кейс «ambiguity-aware few-shot retrieval» поверх сложной (терабайтной, многосхемной) БД. Релевантно для GreenData как пример индустриальной системы, которая публично ставит SOTA на корпоративном Text-to-SQL бенчмарке, не полагаясь только на frontier-модели.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18
  - https://blogs.oracle.com/cloud-infrastructure/oci-gen-ai-tops-spider-2-lite — HTTP 403
  - https://www.emergentmind.com/topics/spider-2-0-benchmark — содержит описание Spider 2.0, без числа SOMA-SQL
  - WebSearch ("SOMA-SQL Spider 2.0 Oracle") вернул заголовок Oracle "Oracle #1 on Spider 2.0 Lite with SOMA-SQL"
- Цитаты (из агрегированного описания в WebSearch):
  - "Oracle achieves #1 on the Spider 2.0 Lite leaderboard, reinforcing its leadership in enterprise NL2SQL with SOMA-SQL"
  - "SOMA-SQL constructs an ambiguity-aware query log offline by generating (NL question, SQL query) pairs aligned with the database schema, and at runtime, retrieves the most relevant examples … as few-shot context to improve the model's ability to interpret and resolve ambiguities"

## Замечание о цифре 72.02%
Конкретное execution-accuracy число «72.02%» в открыто доступных фрагментах не подтверждено. Скорее всего фигурирует в оригинальном Oracle-блоге; для надёжной цитаты нужен доступ к https://blogs.oracle.com/cloud-infrastructure/oci-gen-ai-tops-spider-2-lite через браузер.
