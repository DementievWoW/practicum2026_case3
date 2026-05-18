# CORGI: Agent Bain vs. Agent McKinsey — A New Text-to-SQL Benchmark for the Business Domain

- **Status:** verified
- **Тип:** paper + benchmark
- **Канонический URL:** https://arxiv.org/abs/2510.07309 (arXiv:2510.07309)
- **Год / venue:** 2025 (submission October 8, 2025); under review for ACL ARR — НЕ 2026, как утверждалось пользователем

## Что это
Бенчмарк CORGI: синтетические базы, вдохновлённые реальными компаниями (DoorDash, Airbnb, Lululemon и др.), 10 бизнес-вертикалей в трёх категориях (consumer platforms, retail/commerce, digital services). В среднем 26 таблиц на БД (для сравнения BIRD — 7.3). Четыре уровня сложности вопросов: descriptive, explanatory, predictive, recommendational. Авторы: Yue Li, Ran Tao, Derek Hommel, Yusuf Denizay Dönder, Sungyong Chang, David Mimno, Unso Eun Seo Jo.

## Почему релевантно
CORGI измеряет именно ту способность, которая критична для GreenData: causal/temporal/strategic reasoning поверх многотабличной бизнес-БД. Среднее падение success execution rate (SER) у LLM на CORGI vs BIRD — 33.12%. Это калибровка ожиданий по точности: даже сильные модели на «реалистичном бизнесе» проседают.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2510.07309
- Цитаты:
  - "LLMs exhibit an average 33.12% lower success execution rate (SER) on CORGI compared to existing benchmarks such as BIRD, highlighting the substantially higher complexity of real-world business needs."
  - "CORGI is composed of synthetic databases inspired by enterprises such as Doordash, Airbnb, and Lululemon."
  - "CORGI contains 26 tables per database, which is significantly more than benchmarks such as BIRD (7.3)."

## Коррекция
Пользователь указал «CORGI 2026 benchmark» — фактически статья сабмитнута в октябре 2025, на arXiv 2510.07309. Это не 2026 publication.
