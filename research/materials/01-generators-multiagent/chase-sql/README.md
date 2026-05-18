# CHASE-SQL: Multi-Path Reasoning and Preference Optimized Candidate Selection in Text-to-SQL

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2410.01943
- **Альтернативный URL:** —
- **Год / venue:** arXiv (cs.LG, cs.AI, cs.CL, cs.DB), 2024; цитируется как ICLR 2025 в задании (venue в самом arXiv-листинге не уточнён — пометка «ICLR 2025» в задании пользователя не подтверждена напрямую WebFetch'ем, но не противоречит публикации)

## Что это
CHASE-SQL (Google) — мульти-агентный фреймворк генерации SQL-кандидатов и отбора лучшего. Используются несколько стратегий генерации:
- divide-and-conquer decomposition,
- reasoning based on execution plans,
- synthetic example generation.

Selection agent выполняет pairwise сравнения кандидатов и ранжирует их. Достигнут SOTA execution accuracy 73.01% (dev) и 73.0% (test) на BIRD benchmark.

Авторы: Mohammadreza Pourreza, Hailong Li, Ruoxi Sun, Yeounoh Chung, Shayan Talaei, Gaurav Tarlok Kakkar, Yu Gan, Amin Saberi, Fatma Ozcan, Sercan O. Arik.

## Почему релевантно нашему кейсу
Multi-path generation + preference-optimized selection — естественный паттерн для security pipeline: генерируем N SQL-кандидатов разными стратегиями, security-judge выбирает безопасный, а не «самый правильный» по execution accuracy. Pairwise-сравнение можно адаптировать под критерий «least vulnerable».

## README-превью (только для GitHub репо)
Не применимо — задача указывает только paper, GitHub URL не предоставлен.

## Источник
- WebFetch'нуто: 2026-05-18
  - https://arxiv.org/abs/2410.01943 (успешно)
- Цитаты:
  - "multi-agent modeling to improve candidate generation and selection" (arXiv abstract)
  - "state-of-the-art execution accuracy of 73.0% and 73.01%" (arXiv abstract)
  - "divide-and-conquer decomposition, reasoning based on execution plans, and synthetic example generation" (arXiv abstract)
