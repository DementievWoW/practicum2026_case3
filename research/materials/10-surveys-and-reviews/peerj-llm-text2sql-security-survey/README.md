# A Systematic Survey of LLM-based Text-to-SQL: Methodologies, Security Vulnerabilities, and Future Challenges (PeerJ CS)

- **Status:** verified (corrected URL — исходный `cs-12345` был placeholder)
- **Тип:** paper (peer-reviewed survey, PeerJ Computer Science)
- **Канонический URL:** https://peerj.com/articles/cs-3773/ (PDF: https://peerj.com/articles/cs-3773.pdf)
- **DOI:** 10.7717/peerj-cs.3773
- **Год / venue:** 2026, PeerJ Computer Science, vol. 12, e3773.

## Что это
Систематический обзор Bui CD, Nguyen HH, Ngo TQ, Vu-Thi HK, Nguyen CH, Nguyen DV, Ngo ST. Покрывает современный ландшафт LLM-based Text-to-SQL: методологии (prompt engineering на closed-source vs fine-tuning open-source), бенчмарки, и отдельный фокус на security. Анализ угроз построен через призму OWASP Top 10 для LLM: Prompt Injection (P2SQL), data poisoning / backdoor-инжекции, inference attacks (включая schema-leakage). Обсуждаются future challenges деплоя.

## Почему релевантно
Идеальный «зонтичный» источник для нашего обзорного раздела и motivation: даёт каноничную классификацию угроз для Text-to-SQL пайплайна в PostgreSQL, на которую можно опереться при выборе категорий тест-кейсов для генератора и критериев судьи. Cross-references на ключевые работы (P2SQL, backdoor attacks, schema inference) — готовая библиография.

## README-превью (GitHub)
N/A — журнальная статья.

## Источник
- WebFetch'нуто: 2026-05-18 (PeerJ вернул HTTP 403 при прямом запросе из-за anti-bot; метаданные подтверждены через WebSearch и официальный листинг PeerJ)
- Цитаты (из реферата по результатам поиска): «critical threats identified include Prompt Injection (P2SQL), data poisoning to create backdoors, and inference attacks»; «Modern approaches fall into two main categories: prompt engineering on proprietary models and fine-tuning open-source models».
