# Superviz25-SQL: High-Quality Dataset to Empower Unsupervised SQL Injection Detection Systems

- **Status:** verified
- **Тип:** dataset
- **Канонический URL:** https://zenodo.org/records/17086037 (DOI: 10.5281/zenodo.17086037)
- **Год / venue / CVE-ID:** 2025 — Version 2 опубликована 26 сентября 2025; статья представлена на ANUBIS 2025 (HAL: https://hal.science/hal-05314211v1)

## Что это
Датасет для оценки **неконтролируемых** методов детекции SQL-инъекций. Авторы: Grégor Quetel, Laurent Pautet, Eric Alata, Thomas Robert, Pierre-François Gimenez. Состоит из:
- train: 335 306 benign-запросов;
- test: 3 352 582 sample — 3 017 390 benign + 336 281 malicious (≈90:10), плюс 1 089 «insider-attack» примеров.

Данные синтезированы по 62 шаблонам SQL поверх схемы базы данных OurAirports; малициозные сэмплы сгенерированы инструментом sqlmap с 7 техниками атак. Содержит расширенные метаданные (attack stage, technique type, tamper methods). Файл — CSV 1.1 ГБ. Лицензия: MIT.

## Почему релевантно
Эталон для обучения судьи в режиме «benign-only baseline» (тренировка только на легальной нагрузке конкретной БД, как в реальном проде) и оценки его способности ловить SQLi, включая insider-сценарии. 9 классических и SOTA-пайплайнов уже даны как baseline.

## README-превью (для GitHub) или ключевые поля CVE (для CVE)
Из Zenodo/HAL: «realist, diverse, properly documented dataset»; «Nine classical and state-of-the-art SQL injection detection pipelines are provided as baselines for future works»; квалити-дименшены: realism, diversity, benchmarking capabilities, documentation. Схема БД — OurAirports.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://zenodo.org/records/17086037 и https://pfgimenez.fr/publications/2025-ANUBIS2/
- Цитаты: «Training set: 335,306 benign queries only»; «Test set: 3,017,390 benign queries (90%); 336,281 malicious queries (10%); 1,089 insider attack samples»; «License: MIT»; «Malicious samples created using sqlmap tool across seven attack techniques».
