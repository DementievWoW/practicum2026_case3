# SecureSQL: Evaluating Data Leakage of Large Language Models as Natural Language Interfaces to Databases

- **Status:** verified
- **Тип:** benchmark
- **Канонический URL:** https://aclanthology.org/2024.findings-emnlp.346/
- **Год / venue / CVE-ID:** 2024 — Findings of the Association for Computational Linguistics: EMNLP 2024

## Что это
Бенчмарк для оценки склонности LLM, выступающих в роли Natural Language Interfaces to Databases (NLIDB), сливать чувствительные данные при генерации SQL-запросов. Содержит 932 примера из 34 доменов (медицина, право, финансы, политика). В работе оценено 15 моделей из 6 семейств LLM; лучшая показала 61.7% точности, человек — 94%, многие модели — на уровне случайного выбора. Авторы: Yanqi Song, Ruiheng Liu, Shu Chen, Qianhao Ren, Yu Zhang, Yongqi Yu.

## Почему релевантно
Прямой материал для построения LLM-судьи: целевой бенчмарк, где «успешный» NL→SQL запрос может приводить к утечке защищаемых данных. Подходит как набор валидационных кейсов для проверки post-generation фильтра/судьи, который должен блокировать запросы с риском раскрытия чувствительной информации в PostgreSQL-окружении.

## README-превью (для GitHub) или ключевые поля CVE (для CVE)
Anthology abstract: "We propose SecureSQL, a benchmark to assess the potential of language models to leak sensitive data when generating SQL queries. The benchmark covers 932 samples from 34 different domains, including sensitive topics such as medical, legal, financial, and political aspects." Изучаются 4 типа атак: прямые запросы чувствительных данных, prompt injection, prior-based, inference-based.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://aclanthology.org/2024.findings-emnlp.346/
- Цитаты: «932 samples from 34 different domains»; «Best model achieved 61.7% accuracy; human baseline achieved 94%»; «Most models performed close to or even below the level of random selection».
