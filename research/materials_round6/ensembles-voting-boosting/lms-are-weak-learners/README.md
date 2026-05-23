# Language Models are Weak Learners

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2306.14101
- **Год / venue:** 2023, NeurIPS 2023; CMU
- **Авторы:** Hariharan Manikandan, Yiding Jiang, J. Zico Kolter

## Что это
Показывает, что LLM (через промпт-«саммари» описаний данных) работает как
**weak learner** в boosting-алгоритме — **без какого-либо дообучения**, только
промптингом. На табличных задвах с малым числом точек обходит few-shot и иногда
даже более сложный fine-tuning.

## Почему релевантно нашему кейсу (ADR-0012)
Теоретическая опора «boosting по духу» из ADR: последовательность промпт-учеников,
каждый чинит ошибки предыдущего (наш hard-example loop), реализуема на
замороженной модели. Совместно с [PromptBoosting](../promptboosting/) даёт
честное основание называть каскад судьи boosting'ом, а не только эвристикой.

## Цитаты (verbatim из arXiv abstract)
- "we illustrate the use of a large language model (LLM) as a weak learner in a boosting algorithm applied to tabular data."
- "The model outperforms both few-shot learning and occasionally even more involved fine-tuning procedures, particularly for tasks involving small numbers of data points."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2306.14101 (успешно)
