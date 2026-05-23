# Self-MoA: Rethinking Mixture-of-Agents — Is Mixing Different LLMs Beneficial?

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2502.00674
- **Год / venue:** 2025, arXiv:2502.00674 (cs.CL); Princeton (Li, Lin, Xia, Jin)
- **Авторы:** Wenzhe Li, Yong Lin, Mengzhou Xia, Chi Jin

## Что это
Систематически проверяет, полезно ли смешивать РАЗНЫЕ LLM в ансамбле (MoA).
Вывод: смешивание часто **снижает среднее качество**, потому что MoA очень
чувствителен к качеству участников. Предлагается **Self-MoA** — ансамбль
сэмплов **одной лучшей** модели (плюс `Self-MoA-Seq` для потоковой агрегации).

## Почему релевантно нашему кейсу (ADR-0012)
**Главный аргумент под бюджет ≤30B.** Вместо того чтобы подмешивать слабые
модели разных семейств в скамью судей/генератор, лучше взять ОДНУ сильную
(Qwen-Coder) и гонять **K сэмплов** (implicit ensemble), а разнообразие
добывать промптом/температурой/контекстом. Корректирует наивный тезис
«разнообразие семейств — всё»: разнообразие помогает только если не топит
качество. Подмешивать второе семейство — лишь если абляция это подтвердит.

## Цитаты (verbatim из arXiv abstract)
- "We propose Self-MoA — an ensemble method that aggregates outputs from only the single top-performing LLM."
- "Self-MoA achieves 6.6% improvement over MoA on the AlpacaEval 2.0 benchmark, and an average of 3.8% improvement across various benchmarks."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2502.00674 (успешно)
