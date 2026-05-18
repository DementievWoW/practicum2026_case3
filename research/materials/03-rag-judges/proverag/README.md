# ProveRAG: Provenance-Driven Vulnerability Analysis with Automated Retrieval-Augmented LLMs

- **Status:** verified
- **Тип:** paper (arXiv + IEEE Access)
- **Канонический URL:** https://arxiv.org/abs/2410.17406
- **HTML версия:** https://arxiv.org/html/2410.17406v2
- **Журнал:** IEEE Access, vol. 13, pp. 212815-212826, 2025
- **Год / venue:** 2024-10-22 (arXiv v1); revised 2026-01-23 (v3); опубликовано в IEEE Access 2025
- **Авторы:** Reza Fayyazi, Stella Hoyos Trueba, Michael Zuzak, Shanchieh Jay Yang

## Что это
ProveRAG — LLM-фреймворк для анализа уязвимостей с автоматизированной retrieval augmentation web-данных и встроенным self-evaluation механизмом. Цель — снизить hallucination и omission LLM при разборе security-инфо, поскольку >40K новых CVE в 2024 году вышли после cutoff большинства моделей. Использует cross-reference из двух verifiable sources — NVD и CWE — с провенанс-графом, фиксирующим происхождение и связи извлечённых фактов. Заявленные метрики: 99% accuracy в exploitation strategies, 97% в mitigation strategies; chunking+summarization дают +30% к точности vulnerability retrieval по сравнению с conventional методами.

## Почему релевантно
Эталон LLM + RAG с self-critique над security KB (CWE/NVD) — прямой аналог для PostgreSQL-судьи: можно адаптировать схему провенанса (источник факта → решение судьи) и self-critique loop для уменьшения галлюцинаций при разборе SQLi.

## Цитаты (verbatim из arXiv abstract / WebFetch)
- "The system incorporates a self-critique mechanism to help alleviate the omission and hallucination common in the output of LLMs applied in cybersecurity applications."
- "The system cross-references data from verifiable sources (NVD and CWE), giving analysts confidence in the actionable insights provided."
- "ProveRAG excels in delivering verifiable evidence to the user with over 99% and 97% accuracy in exploitation and mitigation strategies, respectively."

## Верификация
- WebFetch https://arxiv.org/abs/2410.17406 → abstract совпадает с описанием в задаче (self-critique, NVD, CWE)
- Independent confirmations: themoonlight.io review, alphaxiv.org/abs/2410.17406, researchgate publication 398265640, aimodels.fyi
- Journal reference подтверждён: IEEE Access vol.13 pp.212815-212826 (2025)

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2410.17406
- WebSearch: themoonlight.io, alphaxiv.org, aimodels.fyi (множественные independent indexers)
