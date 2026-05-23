# Mixture-of-Agents Enhances Large Language Model Capabilities

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2406.04692
- **Год / venue:** 2024, arXiv:2406.04692 (cs.CL); цит. как ICLR 2025; Together AI / Duke
- **Авторы:** Junlin Wang, Jue Wang, Ben Athiwaratkun, …

## Что это
**Слоистый** ансамбль: каждый слой — несколько LLM-агентов, каждый агент видит
выходы агентов предыдущего слоя как доп. контекст; финальный слой — агрегатор.
Только open-source LLM дают 65.1% на AlpacaEval 2.0 (> GPT-4o 57.5%). Феномен
«collaborativeness»: модель отвечает лучше, видя ответы других, даже более слабых.

## Почему релевантно нашему кейсу (ADR-0012)
Опция «агрегатор-судья поверх голосов» (наш опциональный Stage 2 тай-брейк).
Но для MVP дорого (несколько слоёв × несколько моделей). ⚠️ См.
[Self-MoA](../self-moa/): тот же коллектив утверждает, что под ограничениями
дешевле и часто лучше ансамблировать одну сильную модель, а не смешивать.

## Цитаты (verbatim из arXiv abstract)
- "We propose a new approach that leverages the collective strengths of multiple LLMs through a Mixture-of-Agents (MoA) methodology."
- "MoA models achieves state-of-art performance on AlpacaEval 2.0, MT-Bench and FLASK, surpassing GPT-4 Omni."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2406.04692 (успешно)
