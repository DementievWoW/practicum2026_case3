# More Agents Is All You Need (Agent Forest)

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2402.05120
- **Год / venue:** 2024, TMLR (Transactions on Machine Learning Research); Tencent
- **Авторы:** Junyou Li, Qin Zhang, Yangbin Yu, …

## Что это
Простейший ансамбль: один вход подаётся в LLM N раз → **sampling-and-voting**
(majority) по набору ответов. Метод назван **Agent Forest**. Качество растёт с
числом агентов: 20×Llama2-13B ≈ Llama2-70B, 15×Llama2-70B ≈ GPT-3.5. Ортогонален
CoT и другим усложнениям. Есть **порог сложности**: после некоторого N прироста нет.

## Почему релевантно нашему кейсу (ADR-0012)
База нашего bagging: и для генератора (K кандидатов → выбор), и для судьи
(N голосов). Практический вывод — **N держать небольшим** (≈3–5): после порога
доп. агенты не помогают, а ресурсы on-prem ограничены.

## Цитаты (verbatim из arXiv abstract)
- "simply via a sampling-and-voting method, the performance of large language models (LLMs) scales with the number of agents instantiated."
- "this method, termed as Agent Forest, is orthogonal to existing complicated methods to further enhance LLMs, while the degree of enhancement is correlated to the task difficulty."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2402.05120 (успешно)
