# ADEPT-SQL: A High-performance Text-to-SQL Application for Real-World Enterprise-Level Databases

- **Status:** verified
- **Тип:** paper (system demonstration)
- **Канонический URL:** https://aclanthology.org/2025.acl-demo.27/
- **Год / venue:** 2025, ACL System Demonstrations (Vol. 3), Vienna, Austria

## Что это
Demo-paper ACL 2025: домен-адаптированная система NL→SQL для enterprise-баз. Авторы (Yongnan Chen, Zhuo Chang, Shijia Gu и др.) применяют меньшие open-source LLM с domain-adaptation. Деплоят в нефтегазовой отрасли (petroleum engineering); заявляют 97% execution accuracy на реальных БД, что на 49 абсолютных процентов выше SOTA-бейзлайнов.

## Почему релевантно
Прямой кейс «production NL→SQL на корпоративных БД», где работают не frontier-модели, а маленькие open-source с domain adaptation. Это релевантно для архитектурного выбора GreenData (стоимость, latency, security). Цифра 97% полезна как ориентир-потолок для нишевого домена.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18, URL https://aclanthology.org/2025.acl-demo.27/
- Цитаты:
  - "This approach enables efficient execution using smaller open-source LLMs while maintaining semantic precision. Deployed in petroleum engineering domains, our system achieves 97% execution accuracy on real-world databases, demonstrating 49% absolute improvement over SOTA baselines."
