# Vul-RAG: Enhancing LLM-based Vulnerability Detection via Knowledge-level RAG

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2406.11147
- **Год / venue:** 2024, arXiv:2406.11147 (cs.SE)
- **Авторы:** Xueying Du, Geng Zheng, Kaixin Wang, …

## Что это
**Знаниевый (knowledge-level) RAG** для детекции уязвимостей: из исторических пар
«уязвимость + фикс» дистиллируется многомерное знание (причина, функциональная
семантика, способ исправления) и подтягивается в контекст LLM-детектора. Голые
LLM различают **уязвимый vs пропатченный** код с точностью лишь **0.06–0.14**;
Vul-RAG поднимает accuracy на **16–24%**, ручную детекцию 60%→77%, нашёл 10 багов
в ядре Linux (6 CVE).

## Почему релевантно нашему кейсу (ADR-0012) ⭐⭐
**Прямое обоснование `idx.negatives`** — асимметричного негативного стора судьи.
Killer-факт: различать наши спаренные `sql_bad` vs `sql_good` голой моделью
**очень трудно** → негативные знания судье не «бонус», а необходимость. Наш
датасет (good/bad + `vuln_class` + note) — ровно такой источник знаний «причина +
фикс». Самый близкий внешний прецедент к нашей идее (со стороны судьи).

## Цитаты (verbatim из arXiv abstract)
- "We propose enhancing LLMs with multi-dimensional vulnerability knowledge distilled from historical vulnerabilities and fixes."
- "Vul-RAG improves LLMs with an accuracy increase of 16% - 24% in identifying vulnerable and patched code."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2406.11147 (успешно)
