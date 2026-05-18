# MSc-SQL: Multi-Sample Critiquing Small Language Models For Text-To-SQL Translation

- **Status:** verified (corrected URL)
- **Тип:** paper + github
- **Канонический URL:** https://aclanthology.org/2025.naacl-long.107/ (arXiv: https://arxiv.org/abs/2410.12916, код: https://github.com/layer6ai-labs/msc-sql)
- **Год / venue:** NAACL 2025 (Main, long paper)

## Что это
Метод для text-to-SQL на малых открытых моделях (Mistral, Gemma, Llama3): на одной задаче семплируется множество SQL-кандидатов, после чего обученная модель-критик оценивает их «параллельно», используя метаданные (schema, выполнение и т. п.), и выбирает лучший. Авторы заявляют SOTA среди open-source решений при существенно меньшей стоимости, чем у проприетарных LLM. Конкретные баллы на BIRD/Spider на странице abstract не приведены — заявление «SOTA среди open-source» не подкреплено числами в полученном фетче.

## Почему релевантно
Близкая постановка к нашему циклу «генератор↔судья»: малая модель генерирует много кандидатов SQL, критик ранжирует/правит. Можно переиспользовать идею multi-sample critiquing для аудита PostgreSQL-запросов GreenData без поднятия гигантской модели-судьи.

## README-превью (GitHub-репо)
> Codebase for "MSc-SQL: Multi-Sample Critiquing Small Language Models For Text-To-SQL Translation", accepted to NAACL 2025. Three-stage inference pipeline:
> 1. Schema linking using a PEFT model
> 2. SQL generation across multiple models (Mistral, Gemma, Llama3)
> 3. Result validation and refinement
>
> Users must first download the BIRD benchmark dataset, preprocess it, index the databases, and configure model checkpoints before running inference via `inference.py`.
> License: MIT (Layer 6 AI). 22 commits в main на момент фетча.

## Источник
- WebFetch'нуто: 2026-05-18
- Исходный URL `https://aclanthology.org/2025.naacl-long.122/` оказался чужой работой (Adaptive Prompting for Social Bias Detection). Корректный ID NAACL — `2025.naacl-long.107`.
- Релевантные цитаты: «evaluate multiple outputs simultaneously, achieving state-of-the-art performance compared to other open-source models while remaining competitive with larger models at a much lower cost»; «sampling multiple candidate SQL generations and propose our method, MSc-SQL, to critique them using associated metadata».
