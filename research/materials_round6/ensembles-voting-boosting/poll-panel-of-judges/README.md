# PoLL: Replacing Judges with Juries — Evaluating LLM Generations with a Panel of Diverse Models

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2404.18796
- **Год / venue:** 2024, arXiv:2404.18796 (cs.CL); Cohere (цит. как COLM 2024)
- **Авторы:** Pat Verga, Sebastian Hofstätter, Sophia Althammer, …

## Что это
Вместо одного крупного судьи (GPT-4) — **Panel of LLM evaluators (PoLL)** из
нескольких МЕЛКИХ моделей РАЗНЫХ семейств (Command R + GPT-3.5 + Haiku),
агрегация max/avg voting. Бьёт одного большого судью, **дешевле в 7×**, и даёт
**меньше intra-model bias** за счёт непересекающихся семейств.

## Почему релевантно нашему кейсу (ADR-0012)
Прямая опора для «скамьи судей» (Stage 1). Ключевой посыл: выигрыш даёт
**разнообразие семейств**, а не размер модели — важно под ограниченные ресурсы
заказчика. ⚠️ Читать в паре с [Self-MoA](../self-moa/): под ≤30B разнообразие
семейств не должно топить качество; компромисс — разнообразие через
контекст/температуру (как QLPro), а не через слабые модели.

## Цитаты (verbatim из arXiv abstract)
- "We propose instead to evaluate models using a Panel of LLm evaluators (PoLL)."
- "using a PoLL composed of a larger number of smaller models outperforms a single large judge … while being over seven times less expensive."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2404.18796 (успешно)
