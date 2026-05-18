# DPC: Training-Free Text-to-SQL Candidate Selection via Dual-Paradigm Consistency

- **Status:** verified (corrected URL)
- **Тип:** paper + github
- **Канонический URL:** https://arxiv.org/abs/2604.15163 (код: https://github.com/HKUSTDial/DPC)
- **Год / venue:** ACL 2026 (Main); arXiv v2 от 17.04.2026.

## Что это
Авторы (Boyan Li, Ou Ocean Kun Hei, Yue Yu, Yuyu Luo) формулируют выбор SQL-кандидата как детерминированную верификацию, а не вероятностное «угадывание» LLM-судьёй. Многоагентный пайплайн: SLICER + TESTER строят Minimal Distinguishing Database (MDD), SOLVER проверяет каждый SQL-кандидат, сравнивая его исполнение с параллельным решением на Python/Pandas. Идея: использовать разные failure modes декларативной (SQL) и императивной (Python) парадигм, чтобы отсеять «hallucinated» SQL. Заявленный прирост: «up to 2.2% absolute accuracy» над сильными training-free baselines (например, Self-Consistency) на BIRD и Spider. Per-dataset числа в полученном abstract не приведены.

## Почему релевантно
Прямо адресует слабое место LLM-судей — отсутствие execution oracle. В нашей задаче (аудит PostgreSQL для GreenData) это удобный способ заменить судью на «параллельную реализацию + сравнение результатов», обходя shared blind spots генератора и критика на одной и той же LLM.

## README-превью (GitHub-репо)
> DPC is a training-free method for selecting the best SQL candidate at inference time. Rather than having an LLM judge which SQL is correct, it introduces a parallel Python/Pandas reasoning channel and constructs a "Minimal Distinguishing Database" to verify which SQL solution aligns better with Python execution results.
>
> Installation (uv): `uv sync` (Python 3.10+, deps: openai, pandas, numpy, scipy).
>
> Workflow:
> 1. `bash scripts/run_gen_baseline.sh` — generate candidate SQLs
> 2. `bash scripts/run_dpc_selection.sh` — DPC selection
> 3. `bash scripts/run_eval_ex.sh` — evaluate
>
> Env vars: `MODEL_NAME`, `API_KEY`, `BASE_URL`. License: MIT.

## Источник
- WebFetch'нуто: 2026-05-18, итоговые URL https://arxiv.org/abs/2604.15163 и https://github.com/HKUSTDial/DPC
- Исходный URL `https://arxiv.org/abs/2604.11233` оказался работой про лемматизатор для романшского языка (RUMLEM). ID `2604` сам по себе валиден (апрель 2026), но конкретный номер был placeholder.
- Релевантные цитаты: «Generation-Selection Gap where high potential accuracy (Pass@K) fails to translate into execution accuracy (Pass@1)»; «SLICER and TESTER agent to collaboratively construct a Minimal Distinguishing Database (MDD)»; «validating execution consistency between declarative (SQL) and imperative (Python) paradigms».
