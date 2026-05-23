# PREFER: Prompt Ensemble Learning via Feedback-Reflect-Refine

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2308.12033
- **Год / venue:** 2023, arXiv:2308.12033 (cs.CL); цит. как AAAI 2024
- **Авторы:** Chenrui Zhang, Lin Liu, Jinpeng Wang, …

## Что это
Ансамбль промптов с **обратной связью**: механизм Feedback-Reflect-Refine
рефлексирует над слабыми местами текущих weak learners, и LLM **сам синтезирует
новые промпты** для итеративного улучшения; плюс «prompt bagging» (forward/backward
thinking) для стабильности оценки эффекта промпта.

## Почему релевантно нашему кейсу (ADR-0012)
Прямой мост между ансамблем и нашим узлом **reflector** (Reflexion, ADR-0002):
рефлексия над ошибками → автогенерация новых промптов-учеников = практическая
реализация hard-example mining для скамьи судей/генератора.

## Цитаты (verbatim из arXiv abstract)
- "PREFER builds a feedback mechanism for reflecting on the inadequacies of existing weak learners."
- "our PREFER achieves state-of-the-art performance in multiple types of tasks by a significant margin."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2308.12033 (успешно)
