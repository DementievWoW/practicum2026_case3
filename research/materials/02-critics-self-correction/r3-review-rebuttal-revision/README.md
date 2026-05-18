# R³: "This is My SQL, Are You With Me?" — A Consensus-Based Multi-Agent System for Text-to-SQL

- **Status:** verified (paper); GitHub-репозиторий **NOT FOUND** — НЕ ПОДТВЕРЖДЁН
- **Тип:** paper (workshop)
- **Канонический URL:** https://aclanthology.org/2025.trl-1.4/
- **Альтернативный URL:** https://github.com/1ring2rta/R3 → возвращает HTTP 404, репозиторий не существует (НЕ ПОДТВЕРЖДЕНО — возможно, галлюцинация или репо удалён/перенесён)
- **Год / venue:** Proceedings of the 4th Table Representation Learning Workshop (TRL 2025), Vienna, Austria

## Что это
R³ (Review-Rebuttal-Revision) — консенсусная мульти-агентная система для Text-to-SQL, моделирующая академический цикл рецензирования. Авторы (Hanchen Xia, Feng Jiang, Naihao Deng, Cunxiang Wang, Guojiang Zhao, Rada Mihalcea, Yue Zhang) сообщают SOTA: 89.9 на Spider test и 61.80 на Bird dev. Для Llama-3-8B R³ обходит CoT prompting более чем на 20 пунктов, превосходя даже GPT-3.5 на Spider dev.

Цикл: один агент предлагает SQL («This is my SQL»), другие рецензируют, инициатор пишет rebuttal, по итогам идёт revision до достижения консенсуса.

## Почему релевантно нашему кейсу
Шаблон «Review-Rebuttal-Revision» — прямой кандидат для пайплайна генератор↔судья в GreenData. Аудитор-security агент формулирует претензии (review), SQL-генератор отвечает (rebuttal) и переписывает запрос (revision) до момента, когда уязвимостей не остаётся.

## README-превью (только для GitHub репо)
GitHub-репозиторий https://github.com/1ring2rta/R3 возвращает HTTP 404 (проверено curl и WebFetch). Превью README предоставить невозможно. **НЕ ПОДТВЕРЖДЕНО — возможно, галлюцинация URL** либо репозиторий приватный/удалён.

## Источник
- WebFetch'нуто: 2026-05-18
  - https://aclanthology.org/2025.trl-1.4/ (успешно)
  - https://github.com/1ring2rta/R3 (404)
  - https://raw.githubusercontent.com/1ring2rta/R3/main/README.md (404)
  - https://raw.githubusercontent.com/1ring2rta/R3/master/README.md (404)
- Цитаты:
  - "R3 (Review-Rebuttal-Revision), a consensus-based multi-agent system" (ACL Anthology abstract)
  - "state-of-the-art performance of 89.9 on the Spider test set" и "61.80 on the Bird development set" (ACL Anthology abstract)
