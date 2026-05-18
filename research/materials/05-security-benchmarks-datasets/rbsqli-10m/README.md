# Rule-Based SQL Injection (RbSQLi) Dataset

- **Status:** verified
- **Тип:** dataset
- **Канонический URL:** https://data.mendeley.com/datasets/xz4d5zj5yw/3
- **Год / venue / CVE-ID:** Mendeley Data, Version 3 — 13 июня 2025

## Что это
Большой структурированный датасет для исследований по детектированию SQL-инъекций. Авторы: Mohammad Abu Obaida Mullick, Rezaur Rahman Ratul, Sama Binte Sharif, Sanjida Jannat Anannaya, Mir Moynuddin Ahmed Shibly. Всего 10 304 026 записей: 2 813 146 malicious и 7 490 880 benign. Малициозные пейлоады разбиты на 6 типов SQLi: Union-based (758 600), Stackqueries-based (746 480), Time-based (531 580), Meta-based (481 280), Boolean-based (226 080), Error-based (69 126). Источники пейлоадов: «PayloadsAllTheThings – SQL Injection Payload List» для Union/Time/Error и ChatGPT-генерация для Boolean/Stackqueries/Meta. Лейблирование — rule-based.

## Почему релевантно
Готовый крупный размеченный корпус для тренировки/валидации компонентов LLM-судьи и классических SQLi-детекторов. Подходит для построения precision/recall-метрик, балансировки судьи и сравнения с post-generation фильтрами в Text-to-SQL пайплайне.

## README-превью (для GitHub) или ключевые поля CVE (для CVE)
Из описания на Mendeley: «10,304,026 structured entries, out of which 2,813,146 are labeled as malicious and 7,490,880 as benign». Malicious payloads «categorized into six distinct types» — точные числа см. выше. Пометка: лейблы получены rule-based алгоритмом, что нужно учитывать как ограничение качества (label noise).

## Источник
- WebFetch'нуто: 2026-05-18, URL https://data.mendeley.com/datasets/xz4d5zj5yw/3
- Цитаты: «10,304,026 structured entries»; «six distinct types of SQL injection attacks: Union-based (758,600 samples), Stackqueries-based (746,480 samples), Time-based (531,580 samples), Meta-based (481,280 samples), Boolean-based (226,080 samples), and Error-based (69,126 samples)»; «A rule-based classification algorithm was used to automate the labeling».
