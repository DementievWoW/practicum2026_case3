# NL2SQLBench: A Modular Benchmarking Framework for LLM-Enabled NL2SQL Solutions

- **Status:** verified
- **Тип:** paper + benchmark
- **Канонический URL:** https://arxiv.org/abs/2604.16493
- **PDF VLDB:** https://www.vldb.org/pvldb/vol19/p1001-hou.pdf
- **Год / venue:** 2026, PVLDB Vol. 19, Issue 5, pp. 1001–1015 (VLDB 2026)

## Что это
Первый модульный фреймворк оценки LLM-enabled NL2SQL систем. Разбивает пайплайн на три модуля: **Schema Selection → Candidate Generation → Query Revision**. Для каждого модуля вводит fine-grained метрики качества и эффективности. Авторы: Shizheng Hou, Wenqi Pei, Nuo Chen, Quang-Trung Ta, Peng Lu, Beng Chin Ooi (NUS и др.). Оценивает методы на тестовых датасетах с моделями DeepSeek-V3 и GPT-4o mini.

## Почему релевантно
Модульная декомпозиция (Schema Selection / Candidate Generation / Query Revision) почти один-в-один совпадает с архитектурой, которую мы прорабатываем в GreenData. Метрики per-module позволят честно сравнивать наши изменения по слоям, а не только end-to-end EX. Также авторы прямо называют проблемы существующих бенчмарков (неточные gold SQL, ограничения evaluation-правил) — полезно для нашего обзора.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2604.16493
- Цитаты:
  - "NL2SQLBench, the first modular evaluation and benchmarking framework for LLM-enabled NL2SQL approaches"
  - "decomposes Natural Language to SQL systems into three core components—Schema Selection, Candidate Generation, and Query Revision—with fine-grained metrics to assess effectiveness and efficiency"
  - "significant gaps in existing NL2SQL methods … critical shortcomings in current benchmark datasets and evaluation rules, emphasizing issues such as inaccurate gold SQL annotations"
