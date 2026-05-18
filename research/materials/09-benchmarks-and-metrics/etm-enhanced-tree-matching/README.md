# ETM: Enhanced Tree Matching — Modern Insights into Perspective on Text-to-SQL Evaluation in the Age of LLMs

- **Status:** verified
- **Тип:** paper + open-source metric
- **Канонический URL:** https://arxiv.org/abs/2407.07313
- **Год / venue:** v1 — июль 2024, v3 (актуальная, переименовано в ETM) — июнь 2025, arXiv cs.CL; также опубликовано в MDPI Future Internet 17(8):325

## Что это
ETM (Enhanced Tree Matching) — эволюция ESM+: сравнение SQL-запросов через abstract syntax tree (AST) + набор verifiable equivalence rules, нормализующих запросы перед сравнением. На 9 LLM-based моделях: EXE и ESM дают FP/FN до 23.0%/28.9%, ETM — 0.3%/2.7%. Авторы: Benjamin G. Ascoli, Yasoda Sai Ram Kandikonda, Jinho D. Choi (Emory University).

## Почему релевантно
Прямой кандидат на «правильный» evaluator в GreenData. Текущие EX и ESM искажают картину: первый ложно засчитывает структурно неверные запросы, второй ложно отвергает эквивалентные. ETM даёт более стабильную метрику для LLM-эры, что критично для honest tracking прогресса.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2407.07313
- Цитаты:
  - "ESM's rigid matching overlooks semantically correct but stylistically different queries, whereas EXE can overestimate correctness by ignoring structural errors that yield correct outputs."
  - "EXE and ESM can produce false positive and negative rates as high as 23.0% and 28.9%, while ETM reduces these rates to 0.3% and 2.7%, respectively."
  - "We release our ETM script as open source, offering the community a more robust and reliable approach to evaluating Text-to-SQL."

## Замечание
ETM и ESM+ — одна и та же работа, под разными именами (v1 vs v3 arXiv). См. также материал `esm-plus`.
