# PromptBoosting: Black-Box Text Classification with Ten Forward Passes

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2212.09257
- **Год / venue:** 2023, ICML 2023
- **Авторы:** Bairu Hou, Joe O'Connor, Jacob Andreas, …

## Что это
**Boosting на ЗАМОРОЖЕННЫХ весах через промпты.** Weak learner = промпт ×
элемент выходного распределения модели; такие weak learners ансамблируются
классическим **AdaBoost**. Только forward-проходы, **без backward** — обучение
на порядок дешевле других black-box методов.

## Почему релевантно нашему кейсу (ADR-0012)
Уточняет наш тезис «настоящего boosting с замороженными LLM нет». **Есть** —
PromptBoosting. Значит каскад судьи на трудных классах (PRIV_ESCALATE,
PLPGSQL_UNSAFE, SQL_INJ_TIME) можно строить как полноценный AdaBoost над
промпт-вариантами одной модели, а не только как эвристический «каскад специалистов».

## Цитаты (verbatim из arXiv abstract)
- "These weak learners are then ensembled using the AdaBoost algorithm."
- "PromptBoosting achieves state-of-the-art performance in multiple black-box few-shot classification tasks … while training 10x faster than existing black-box methods."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2212.09257 (успешно)
