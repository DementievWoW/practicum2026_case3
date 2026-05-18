# MageSQL: Demonstration of a Multi-agent Framework for Text to SQL Applications with LLMs

- **Status:** verified (corrected URL и corrected description — в задании MageSQL ошибочно описан как «spatial SQL»; реальная работа CIKM 2024 — общий text-to-SQL multi-agent demo; spatial Text-to-SQL — это другая, отдельная статья)
- **Тип:** paper (CIKM 2024 demo) + сопутствующая arXiv-расширенная версия
- **Канонический URL:** https://dl.acm.org/doi/10.1145/3627673.3679216
- **Альтернативный URL:**
  - https://megagon.ai/publications/demonstration-of-a-multi-agent-framework-for-text-to-sql-applications-with-large-language-models/
  - https://arxiv.org/abs/2504.02055 (расширенная версия "MageSQL: Enhancing In-context Learning for Text-to-SQL Applications with Large Language Models")
  - **Отдельная работа про spatial Text-to-SQL** (НЕ MageSQL): https://arxiv.org/abs/2510.21045 "From Questions to Queries: An AI-powered Multi-Agent Framework for Spatial Text-to-SQL" (Khosravi Kazazi et al.)
- **Год / venue:** CIKM 2024 (33rd ACM International Conference on Information and Knowledge Management), Demo track

## Что это
MageSQL — мульти-агентный демо-фреймворк (Megagon Labs) для Text-to-SQL с акцентом на оркестрацию агентов в пайплайн. Авторы: Chen Shen, Jin Wang, Sajjadur Rahman, Eser Kandogan. Пользователь может добавлять/изменять агентов с разной функциональностью, кастомизировать промпты, отлаживать результаты на конкретных примерах. Цель — сделать LLM-based text-to-SQL более прозрачным и настраиваемым через UI.

**Важно:** работа НЕ про spatial SQL (как было заявлено в задании пользователя). Spatial Text-to-SQL — это отдельная статья 2025 года arXiv 2510.21045 авторов Ali Khosravi Kazazi, Zhenlong Li и др., где описан мульти-агентный фреймворк (interpretation → schema grounding → logical planning → SQL generation → execution-based review) с поддержкой PostGIS, достигший 81.2% на KaggleDBQA и 87.7% на собственном SpatialQueryQA.

## Почему релевантно нашему кейсу
MageSQL — образец конфигурируемого UI для отладки multi-agent пайплайнов; полезно как референс UX для SQL Security System. Spatial-аналог (2510.21045) интересен из-за PostGIS-агента и «execution-based review» — оба этих элемента совпадают с целью GreenData (PostgreSQL + аудит).

## README-превью (только для GitHub репо)
Не применимо — публичного GitHub-репозитория CIKM-демо не предоставлено (по состоянию на 2026-05-18).

## Источник
- WebFetch'нуто: 2026-05-18
  - https://dl.acm.org/doi/10.1145/3627673.3679216 (через WebSearch metadata)
  - https://megagon.ai/publications/demonstration-of-a-multi-agent-framework-for-text-to-sql-applications-with-large-language-models/ (успешно)
  - https://arxiv.org/abs/2510.21045 (успешно — для spatial-аналога)
- Цитаты:
  - "Demonstration of a Multi-agent Framework for Text to SQL Applications with Large Language Models", Chen Shen, Jin Wang, Sajjadur Rahman, Eser Kandogan, CIKM 2024 Demo (megagon.ai)
  - "This work addresses general text-to-SQL conversion, not spatial SQL specifically" (Megagon page summary)
  - "a multi-agent framework that addresses these coupled challenges through staged interpretation, schema grounding, logical planning, SQL generation, and execution-based review" (2510.21045 abstract, spatial paper)
