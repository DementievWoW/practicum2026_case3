# Materials · круг 6 — ансамбли gen/judge + асимметричный retrieval

**Новый ресёрч** (отделён от «старого» [`research/materials/`](../materials/)).
Собран под [ADR-0012](../../docs/adr/0012-ensemble-gen-judge-asymmetric-retrieval.md):
мультиагент с bagging/boosting нескольких моделей для генератора и судьи +
асимметричный few-shot (судье — уязвимые примеры, генератору — безопасные).

Сводка и маппинг находок на наш дизайн — в [`research/06_ensemble_gen_judge.md`](../06_ensemble_gen_judge.md).

Формат карточек — как в старом materials: статус, канонический URL, авторы, год,
«что это», «почему релевантно», verbatim-цитаты, источник. Все 12 — `verified`
(WebFetch abstract, 2026-05-23/24): URL резолвится, цитаты дословные.

## Группы

| # | Группа | Кол-во | Что внутри |
|---|---|---|---|
| A | [ensembles-voting-boosting/](ensembles-voting-boosting/) | 9 | Ансамбли LLM: bagging/voting/boosting, жюри судей, Self-MoA |
| B | [rag-judges-security/](rag-judges-security/) | 3 | Знаниевый RAG для детекции уязвимостей (негативный стор судьи) |

## A — ensembles-voting-boosting (9)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [self-moa](ensembles-voting-boosting/self-moa/) ⭐⭐ | paper | verified | https://arxiv.org/abs/2502.00674 |
| [poll-panel-of-judges](ensembles-voting-boosting/poll-panel-of-judges/) ⭐ | paper | verified | https://arxiv.org/abs/2404.18796 |
| [more-agents-agent-forest](ensembles-voting-boosting/more-agents-agent-forest/) | paper | verified | https://arxiv.org/abs/2402.05120 |
| [mixture-of-agents](ensembles-voting-boosting/mixture-of-agents/) | paper | verified | https://arxiv.org/abs/2406.04692 |
| [qlpro-triple-voting](ensembles-voting-boosting/qlpro-triple-voting/) ⭐ | paper | verified | https://arxiv.org/abs/2506.23644 |
| [llm-judge-reliability](ensembles-voting-boosting/llm-judge-reliability/) | paper | verified | https://arxiv.org/abs/2412.12509 |
| [promptboosting](ensembles-voting-boosting/promptboosting/) | paper | verified | https://arxiv.org/abs/2212.09257 |
| [lms-are-weak-learners](ensembles-voting-boosting/lms-are-weak-learners/) | paper | verified | https://arxiv.org/abs/2306.14101 |
| [prefer-prompt-ensemble](ensembles-voting-boosting/prefer-prompt-ensemble/) | paper | verified | https://arxiv.org/abs/2308.12033 |

## B — rag-judges-security (3)

| Материал | Тип | Статус | Канонический URL |
|---|---|---|---|
| [vul-rag](rag-judges-security/vul-rag/) ⭐⭐ | paper | verified | https://arxiv.org/abs/2406.11147 |
| [mulvul](rag-judges-security/mulvul/) | paper | verified | https://arxiv.org/abs/2601.18847 |
| [llm-security-detector-robustness](rag-judges-security/llm-security-detector-robustness/) | paper | verified | https://arxiv.org/abs/2411.18216 |

## Самое важное (⭐⭐)
- [self-moa](ensembles-voting-boosting/self-moa/) — как строить ансамбль под ≤30B (одна сильная модель × K сэмплов, а не смесь слабых).
- [vul-rag](rag-judges-security/vul-rag/) — обоснование негативного стора судьи (голая LLM различает vuln/patched лишь 0.06–0.14).
