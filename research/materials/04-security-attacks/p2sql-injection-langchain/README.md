# P2SQL Injection in LangChain (Prompt-to-SQL Injections in LLM-Integrated Web Applications)

- **Status:** verified
- **Тип:** paper (IEEE/ACM ICSE 2025; preprint arXiv 2023, v4 2025)
- **Канонический URL:** https://ieeexplore.ieee.org/document/11029790 (платный) — открытый препринт: https://arxiv.org/abs/2308.01990
- **DOI:** 10.1109/ICSE55347.2025.00007
- **Год / venue:** 2025, IEEE/ACM 47th International Conference on Software Engineering (ICSE 2025), Research Track. Препринт — arXiv 2023, обновлён до v4 в 2025.

## Что это
Систематическое исследование уязвимостей класса P2SQL (Prompt-to-SQL) в веб-приложениях, построенных на LLM-фреймворках LangChain и LlamaIndex. Авторы (Rodrigo Pedro, Daniel Castro, Paulo Carreira, Nuno Santos) показывают, как несанированные пользовательские промпты конвертируются цепочкой агентов в SQL и приводят к инъекциям. Протестированы 7 ведущих LLM, продемонстрирована широкая подверженность; в пяти реальных приложениях найдены практические P2SQL-уязвимости. Предложены 4 защитных техники, реализуемые как расширения для LangChain.

## Почему релевантно
Базовая референс-работа для нашего проекта: задаёт таксономию P2SQL-атак (jailbreak SQL, бесконтрольный CRUD через цепочки), которую генератор должен воспроизводить в тест-кейсах, а судья — детектировать в выходе аудируемого PostgreSQL-агента. Защитные техники из работы (валидаторы, ограничение ролей, sandbox-схемы) — прямые кандидаты для нашего deterministic-validator слоя.

## README-превью (GitHub)
N/A — это статья, не репозиторий. Авторы публиковали реализацию в составе материалов ICSE; ссылку на repo нужно искать в финальной версии PDF.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2308.01990 (IEEE URL вернул HTTP 418 для анонимного доступа, верифицирован через WebSearch + ICSE 2025 page + ACM DL)
- Цитаты: «We find that LLM-integrated applications based on Langchain are highly susceptible to P2SQL injection attacks»; «we propose four effective defense techniques that can be integrated as extensions to the Langchain framework».
