# ESM+: Exact Set Matching Plus

- **Status:** verified (с уточнением: в актуальной версии работы метрика переименована в ETM)
- **Тип:** paper + open-source metric
- **Канонический URL (старая версия v1):** https://arxiv.org/html/2407.07313v1 (ESM+)
- **Канонический URL (актуальная v3):** https://arxiv.org/abs/2407.07313 (переименовано в ETM)
- **Реализация:** https://github.com/bossben/ESMp
- **Год / venue:** v1 — июль 2024; v3 — июнь 2025; опубликовано также в MDPI Future Internet (17(8):325)

## Что это
ESM+ — новая метрика для Text-to-SQL, исправляющая недостатки Execution Accuracy (EXE) и Exact Set Matching (ESM). По данным первой версии работы: EXE и ESM дают FP/FN до 11.3%/13.9%, у ESM+ — 0.1%/2.6%. По актуальной (v3, переименованной в ETM): EXE и ESM показывают FP/FN до 23.0%/28.9%, ETM снижает до 0.3%/2.7%. Идея: использовать AST-сравнение + verifiable equivalence rules для нормализации запросов перед сопоставлением.

## Почему релевантно
GreenData нужен честный evaluator, который не штрафует за стилистические различия эквивалентных SQL и не пропускает структурно неверные запросы со случайно совпавшим результатом. ESM+/ETM — потенциальная замена/дополнение к нашему текущему EX/EM.

## README-превью (для GitHub bossben/ESMp)
Из агрегированного описания: «The ESM+ script is released as open-source for the community. The metric includes options for disabling specific checks and supports detailed analysis of evaluation rules.» Полный README не извлекался (репозиторий назван по старой версии — `ESMp`).

## Источник
- WebSearch'нуто: 2026-05-18, "Exact Set Matching Plus text-to-SQL metric" и "ETM text-to-SQL"
- Цитаты:
  - "ESM+ calculates semantic accuracy with a lower rate of false positives than Execution accuracy and a lower rate of false negatives than Exact Set Matching"
  - "EXE and ESM have high false positive and negative rates of 11.3% and 13.9%, while ESM+ gives those of 0.1% and 2.6% respectively"

## Коррекция
ESM+ — это **рабочее название первой версии** статьи Ascoli et al. (2024). В актуальной версии метрика переименована в **ETM** (см. отдельный материал `etm-enhanced-tree-matching`). Цитировать стоит ETM (v3), но имя ESM+ узнаваемо в литературе.
