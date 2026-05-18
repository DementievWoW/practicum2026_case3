# PremSQL (Prem AI)

- **Status:** verified (GitHub доступен; pypi и premai.io вернули 404/ошибку, но репозиторий и landing premai.io/premsql существуют)
- **Тип:** github / open-source library
- **Канонический URL:** https://github.com/premAI-io/premsql
- **Сопутствующие URL:**
  - https://www.premai.io/premsql (на момент проверки 2026-05-18: HTTP 404)
  - https://pypi.org/project/premsql/ (на момент проверки: страница не отрендерилась, ошибка загрузки)
- **Год / venue:** 2024–2025, open-source (Prem AI)

## Что это
Open-source библиотека для построения локальных Text-to-SQL пайплайнов на малых LLM. Local-first архитектура, end-to-end pipeline: датасеты (BirdBench, Spider, домены, Gretel), генераторы, executors, evaluators (Execution Accuracy, VES), error handlers с self-correction, fine-tuning (LoRA / QLoRA / full), agents, playground. Поддерживает PremAI, Ollama, HuggingFace, Apple MLX, OpenAI. Собственная модель Prem-1B-SQL — 51.54% на BirdBench private.

## Почему релевантно
Готовый референс-стек, очень близкий по идеологии к GreenData SQL Security: local-first, малые модели, self-correction, evaluation на стандартных бенчмарках. Можно заимствовать структуру executor/evaluator и интерфейс error-handlers, а также использовать как baseline для сравнения.

## README-превью (для GitHub)
Ключевые секции README:
- What is PremSQL: end-to-end local Text-to-SQL
- Features: Local-first, Multiple Connectors, Customizable Datasets, Executors & Evaluators, Generators, Error Handling & Self-Correction, Fine-Tuning Support, Agents & Playground
- Installation: `pip install -U premsql` (Python 3.8+)
- Model Support: Prem-1B-SQL (51.54% BirdBench private), HuggingFace, Ollama, OpenAI
- Core Components: Datasets, Generators, Executors, Evaluators, Error Handlers, Tuner, Agents, Playground

## Источник
- WebFetch'нуто: 2026-05-18
  - https://github.com/premAI-io/premsql — OK, контент извлечён
  - https://www.premai.io/premsql — HTTP 404
  - https://pypi.org/project/premsql/ — страница не загрузилась
- Цитаты:
  - "PremSQL is an open-source library enabling developers to build secure, fully local Text-to-SQL solutions using small language models"
  - "Prem-1B-SQL (achieving 51.54% accuracy on BirdBench private dataset)"
