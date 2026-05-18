# SQLCritic: Correcting Text-to-SQL Generation via Clause-wise Critic

- **Status:** verified (corrected URL)
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2503.07996 (v3 от мая 2025)
- **Год / venue:** arXiv preprint, март 2025 (последняя редакция 21.05.2025). Venue не указан.

## Что это
Авторы (Jikai Chen, Leilei Gan, Ziyu Zhao, Zechuan Wang, Dong Wang, Chenyi Zhuang) предлагают критик-фреймворк для Text-to-SQL, работающий пощёлочно (clause-wise): на каждом клозе SQL критик локализует и поясняет синтаксические и семантические ошибки. Введён бенчмарк SQLCriticBench и адаптивный вариант DPO, где β-коэффициент меняется в зависимости от clause-level рассогласования между preferred/dispreferred критиками. Авторы заявляют «significantly improves SQL accuracy on BIRD and Spider»; конкретные числовые приросты в полученном abstract не указаны (утверждение не подтверждено числами).

## Почему релевантно
Пощёлочный (clause-wise) критик — это ровно то, что нужно для аудита PostgreSQL-запросов GreenData: можно вешать judge на отдельные WHERE/JOIN/GROUP BY и получать интерпретируемые претензии, а не «плохо/хорошо».

## README-превью (GitHub-репо)
Ссылки на код в abstract нет; репозиторий в полученном контенте не указан.

## Источник
- WebFetch'нуто: 2026-05-18, итоговый URL https://arxiv.org/abs/2503.07996
- Исходный URL `https://ar5iv.labs.arxiv.org/html/2503.12345` — placeholder, ar5iv вернул «Fatal error / Untitled Document».
- Релевантные цитаты: «clause-wise critique generation task along with a benchmark, SQLCriticBench»; «variant of DPO ... β coefficient is adaptively changed according to the clause-level inconsistencies»; «combines structured execution feedback with a trained critic agent that provides detailed, interpretable critiques».
