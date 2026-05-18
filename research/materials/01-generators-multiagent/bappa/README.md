# BAPPA: Benchmarking Agents, Plans, and Pipelines for Automated Text-to-SQL Generation

- **Status:** verified
- **Тип:** paper + github repo
- **Канонический URL:** https://arxiv.org/abs/2511.04153
- **Альтернативный URL:** https://github.com/treeDweller98/bappa-sql
- **Год / venue:** arXiv (cs.CL), submitted November 6, 2025

## Что это
Работа сравнивает три мульти-агентных LLM-пайплайна для перевода естественного языка в SQL: (1) Multi-agent discussion (агенты итеративно критикуют и уточняют запрос, судья синтезирует финальный ответ); (2) Planner-Coder (модель-планировщик строит план, кодер пишет SQL); (3) Coder-Aggregator (несколько кодеров генерируют параллельно, reasoning-агент выбирает лучший). Эксперименты на open-source моделях показали прирост Execution Accuracy до 10.6% для Qwen2.5-7b-Instruct, лучший пайплайн дал 56.4% на Bird-Bench Mini-Dev.

Авторы: Fahim Ahmed, Md Mubtasim Ahasan, Jahir Sadik Monon, Muntasir Wahed, M Ashraful Amin, A K M Mahbubur Rahman, Amin Ahsan Ali.

## Почему релевантно нашему кейсу
Прямая иллюстрация цикла «генератор-судья» на малых open-source моделях, релевантного для GreenData SQL Security System: можно взять Multi-agent discussion как опору архитектуры, где роль «судьи» выполняет аудитор-security, а коммиттер — SQL-генератор.

## README-превью (только для GitHub репо)
Согласно README репозитория treeDweller98/bappa-sql:

> "we propose MAG-SQL..." (формулировка отсутствует в этом репо — относится к другой работе)

Реальные секции, подтверждённые через WebFetch raw README:
- Описание трёх пайплайнов (Multi-agent discussion, Planner-Coder, Coder-Aggregator)
- Setup: Python 3.13, зависимости включают pandas, wandb, vllm, func_timeout
- Конфигурация: secrets.env для API-ключей, нужно модифицировать run_exp.sh
- Лицензия: Apache 2.0

## Источник
- WebFetch'нуто: 2026-05-18
  - https://arxiv.org/abs/2511.04153
  - https://github.com/treeDweller98/bappa-sql
  - https://raw.githubusercontent.com/treeDweller98/bappa-sql/main/README.md
- Цитаты:
  - "Multi-Agent discussion can improve small model performance, with up to 10.6% increase in Execution Accuracy" (arXiv abstract)
  - "agents iteratively critique and refine SQL queries, and a judge synthesizes the final answer" (README)
