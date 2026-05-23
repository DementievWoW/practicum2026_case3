# MulVul: Retrieval-augmented Multi-Agent Code Vulnerability Detection via Cross-Model Prompt Evolution

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2601.18847
- **Год / venue:** 2026, arXiv:2601.18847 (cs.SE)
- **Авторы:** Zihan Wu, Jie Xu, Yun Peng, …

## Что это
**Мультиагентная** детекция уязвимостей с RAG и эволюцией промптов между
моделями. Стратегия coarse-to-fine: агент-**Router** предсказывает top-k грубых
категорий и направляет вход специализированным агентам-**Detector**, которые
определяют точные типы. На 130 типах CWE — 34.79% Macro-F1, +41.5% к лучшему baseline.

## Почему релевантно нашему кейсу (ADR-0012)
Созвучно нашему каскаду судьи: грубый отбор (Router) → специалисты по классам
(Detector) — это и есть «boosting-каскад специалистов» по vuln_class из ADR-0012,
но в детекции кода. Подтверждает связку «RAG + мультиагент + специализация по
классам» как рабочий паттерн.

## Цитаты (verbatim из arXiv abstract)
- "MulVul adopts a coarse-to-fine strategy: a Router agent first predicts the top-k coarse categories and then forwards the input to specialized Detector agents, which identify the exact vulnerability types."
- "Evaluated on 130 CWE types, MulVul achieves 34.79% Macro-F1, outperforming the best baseline by 41.5%."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2601.18847 (успешно)
