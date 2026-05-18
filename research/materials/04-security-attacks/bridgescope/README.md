# BridgeScope: A Universal Toolkit for Bridging Large Language Models and Databases

- **Status:** verified (corrected URL — исходный ADS ID `2025arXiv250612345B` был placeholder)
- **Тип:** paper (arXiv preprint; принят на CIDR 2026)
- **Канонический URL:** https://arxiv.org/abs/2508.04031 (HTML: https://arxiv.org/html/2508.04031v1, PDF: https://arxiv.org/pdf/2508.04031). Конференционная версия: https://www.vldb.org/cidrdb/papers/2026/p4-weng.pdf
- **Год / venue:** Submitted 2025-08-06, accepted to CIDR 2026.

## Что это
Авторы Lianggui Weng, Dandan Liu, Rong Zhu, Bolin Ding, Jingren Zhou представляют универсальный toolkit для связи LLM-агентов с БД. Три ключевых инновации:
1. Модульное разбиение SQL-операций на мелкозернистые tools (context retrieval, CRUD, ACID-транзакции) — точный контроль функциональности.
2. Согласование реализаций tools с привилегиями БД и пользовательскими security-политиками — отводит LLM от небезопасных/несанкционированных операций.
3. Proxy-механизм для inter-tool передачи данных в обход LLM-канала, снижающий потребление токенов.

Эвалюация на двух новых бенчмарках: эффективность работы агента с БД улучшена, токены сокращены до 80% за счёт security-awareness, поддерживаются data-intensive воркфлоу. Выпущена open-source реализация для **PostgreSQL**.

## Почему релевантно
Прямо ложится на наш стек: PostgreSQL + LLM-агент. BridgeScope даёт референс-архитектуру безопасной toolset-обёртки (разрешения, ACID, прокси), которую можно использовать как baseline-инструмент в нашем генератор-судья эксперименте — генерировать атаки и проверять, ловит ли BridgeScope их в сравнении с нашим валидатором.

## README-превью (GitHub)
Open-source реализация для PostgreSQL анонсирована в статье; конкретная ссылка на репозиторий не указана в abstract — искать в финальном PDF.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2508.04031
- Цитаты: «aligns tool implementations with both database privileges and user security policies to steer LLMs away from unsafe or unauthorized operations»; «reduces token usage by up to 80% through improved security awareness»; «open-source implementation of BridgeScope for PostgreSQL».
