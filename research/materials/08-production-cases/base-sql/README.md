# BASE-SQL (CycloneBoy/base_sql)

- **Status:** verified
- **Тип:** github (open-source) + сопутствующая статья
- **Канонический URL:** https://github.com/CycloneBoy/base_sql
- **Год / venue:** 2025

## Что это
BASE-SQL — pipeline-based подход к Text-to-SQL, использующий fine-tuning open-source моделей. Четырёхкомпонентный пайплайн: (1) Schema Linking, (2) Candidate SQL Generate, (3) SQL Revision, (4) SQL Merge Revision. Эффективность: ~5 LLM-вызовов на один SQL. Заявленные результаты: 67.47% на BIRD dev, 88.9% на Spider test. Авторы: Lei Sheng, Shuai-Shuai Xu, Wei Xie.

## Почему релевантно
Это компактный, воспроизводимый референс-пайплайн с разделением ответственности (генерация + ревизия + объединение). Архитектурно близок к тому, что планируется в GreenData. Использует open-source LLM — подходит для воспроизводства как baseline.

## README-превью (для GitHub)
Ключевые секции:
- Overview: pipeline-based Text-to-SQL с fine-tuning open-source моделей
- Pipeline: Schema Linking → Candidate SQL Generate → SQL Revision → SQL Merge Revision
- Efficiency: ~5 LLM calls per SQL generation
- Performance: 67.47% BIRD dev, 88.9% Spider test
- Status: 13 stars, 1 fork; code organization and model release pending (TODO)

## Источник
- WebFetch'нуто: 2026-05-18, URL https://github.com/CycloneBoy/base_sql
- Цитаты:
  - "Results demonstrate superiority over other open source methods and competitive performance against several methods using the GPT-4o closed-source model"
  - "Four-component pipeline: Schema Linking, Candidate SQL Generate, SQL Revision, and SQL Merge Revision"
