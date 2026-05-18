# MAG-SQL: Multi-Agent Generative Approach with Soft Schema Linking and Iterative Sub-SQL Refinement

- **Status:** verified (corrected URL — оригинальный semanticscholar-URL в задании был неполным; найдена точная arXiv-страница)
- **Тип:** paper + github repo
- **Канонический URL:** https://arxiv.org/abs/2408.07930
- **Альтернативный URL:** https://github.com/Lancelot-Xie/MAG-SQL
- **Год / venue:** arXiv (cs.CL), submitted August 15, 2024 (last revised November 7, 2024)

## Что это
MAG-SQL — мульти-агентная архитектура для Text-to-SQL, состоящая из четырёх компонент:
1. **Soft Schema Linker** — entity-based отбор колонок с использованием саммари таблиц.
2. **Targets-Conditions Decomposer** — декомпозирует сложные вопросы на целевые поля и условия.
3. **Sub-SQL Generator** — итеративно генерирует подзапросы.
4. **Sub-SQL Refiner** — внешнее «надзирающее» уточнение каждого шага.

На BIRD с GPT-4 достигнут execution accuracy 61.08% против 46.35% baseline GPT-4 и 57.56% MAC-SQL. Авторы: Wenxuan Xie, Gaochen Wu, Bowen Zhou.

## Почему релевантно нашему кейсу
Soft schema linking + декомпозиция «таргеты-условия» помогают точечно строить корректные WHERE/JOIN и снижают риск SQL-инъекций через жёсткое связывание сущностей со схемой. Iterative Sub-SQL Refiner — готовый паттерн для security-надзирателя в цикле.

## README-превью (только для GitHub репо)
Из README репозитория Lancelot-Xie/MAG-SQL (HTML-страница GitHub, raw недоступен):

> "we propose MAG-SQL, a multi-agent generative approach with soft schema linking and iterative Sub-SQL refinement"

Реальные подтверждённые секции:
- Setup: Python 3.9, OpenAI API 0.28.1, Conda environment, requirements.txt, NLTK data.
- Data: BIRD benchmark, eval data в `data/bird/dev/`.
- Stars: 19, License: MIT.
- Citation: arXiv 2408.07930.
- Project builds upon MAC-SQL.

## Источник
- WebFetch'нуто: 2026-05-18
  - https://arxiv.org/abs/2408.07930 (успешно)
  - https://github.com/Lancelot-Xie/MAG-SQL (успешно)
  - https://raw.githubusercontent.com/Lancelot-Xie/MAG-SQL/main/README.md (404 — взят HTML-fallback)
- Цитаты:
  - "MAG-SQL achieved an execution accuracy of 61.08%, compared to the baseline accuracy of 46.35% for vanilla GPT-4 and the baseline accuracy of 57.56% for MAC-SQL" (arXiv abstract)
  - "entity-based method with tables' summary is used to select the columns in database" (arXiv abstract)
