# Zero-Knowledge Schema Inference Attacks in Text-to-SQL Systems

- **Status:** verified (corrected URL — оригинальный arXiv ID `2506.03556` указывал на постороннюю работу про FPGA-тесты)
- **Тип:** paper (arXiv preprint + NAACL 2025 Findings)
- **Канонический URL:** https://arxiv.org/abs/2406.14545 (HTML: https://arxiv.org/html/2406.14545v2). Опубликованная версия: https://aclanthology.org/2025.findings-naacl.386/
- **Год / venue:** Submitted 2024-06-20, accepted Findings of NAACL 2025; последняя версия arXiv обновлена в 2025.

## Что это
Работа Đorđe Klisura и Anthony Rios «Unmasking Database Vulnerabilities: Zero-Knowledge Schema Inference Attacks in Text-to-SQL Systems». Авторы предлагают атаку, при которой адверсарий, не имея доступа к схеме БД, систематически зондирует text-to-SQL модель специально сконструированными вопросами и через суррогатную модель GPT-4 интерпретирует SQL-выходы, восстанавливая таблицы, колонки и типы данных. Достигают F1 ≈ 0.99 для генеративных моделей и ≈ 0.78 для fine-tuned. Также обсуждаются защитные меры и их ограничения.

## Почему релевантно
Прямая модель угроз для нашего генератор-судья пайплайна: восстановление скрытой схемы PostgreSQL через ответы агента — типовая «утечка» которую судья должен детектировать. Метрика F1 даёт ориентир для baseline в наших экспериментах по schema-leakage и оценке оборонительных промптов/маскирующих фильтров.

## README-превью (GitHub)
N/A. Авторская реализация в репозитории не подтверждена в abstract; нужно искать по footnote в PDF.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2406.14545
- Цитаты: «we systematically probe text-to-SQL models with specially crafted questions and leverage a surrogate GPT-4 model to interpret the outputs»; «F1 scores of up to .99 for generative models and .78 for fine-tuned models, underscoring the severity of schema leakage».
