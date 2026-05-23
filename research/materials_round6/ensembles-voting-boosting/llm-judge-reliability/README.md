# Can You Trust LLM Judgments? Reliability of LLM-as-a-Judge

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2412.12509
- **Год / venue:** 2024, arXiv:2412.12509 (cs.CL)
- **Авторы:** Kayla Schroeder, Zach Wood-Doughty

## Что это
Вводит строгий статистический фреймворк оценки **надёжности** LLM-судей
(через McDonald's omega). Показывает: одиночный судья нестабилен; усреднение по
нескольким сэмплам важно. Майорити-voting повышает надёжность, но **не лечит
систематические (скоррелированные) смещения**; экспертиза судьи контекст-зависима.

## Почему релевантно нашему кейсу (ADR-0012)
Подтверждает наш **главный риск** — корреляция участников ансамбля судьи.
Отсюда: (1) разнообразие участников критично; (2) для recall-критичной задачи
полезен minority-veto-режим (любой уверенный голос → флаг), но он раздувает FP →
обязательна **калибровка порога** суммы risk_score на 200 good-двойниках датасета.

## Цитаты (verbatim из arXiv abstract)
- "we introduce a novel framework for rigorously evaluating the reliability of LLM judgments, leveraging McDonald's omega."
- "we demonstrate the limitations of fixed randomness and the importance of considering multiple samples, which we show has significant implications for downstream applications."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2412.12509 (успешно)
