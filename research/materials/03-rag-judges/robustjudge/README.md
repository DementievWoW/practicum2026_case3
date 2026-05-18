# RobustJudge / "LLMs Cannot Reliably Judge (Yet?)"

- **Status:** verified
- **Тип:** paper (arXiv) + github repository
- **Канонический URL (paper):** https://arxiv.org/abs/2506.09443
- **PDF:** https://arxiv.org/pdf/2506.09443
- **GitHub:** https://github.com/S3IC-Lab/RobustJudge
- **Год / venue:** 2025-06-11 (v1); revised 2025-11-16 (v2)
- **Авторы:** Songze Li, Chuokun Xu, Jiaying Wang, Xueluan Gong, Chen Chen, Jirui Zhang, Jun Wang, Kwok-Yan Lam, Shouling Ji

## Что это
Paper "LLMs Cannot Reliably Judge (Yet?): A Comprehensive Assessment on the Robustness of LLM-as-a-Judge" вводит **RobustJudge** — fully automated, scalable framework для систематической оценки robustness LLM-as-a-Judge систем под атаками. Исследование охватывает 15 attack methods, 7 defense strategies и 12 моделей (числа подтверждены в abstract). Анализирует влияние prompt-template design и model selection, оценивает security real-world deployments (deployment на Alibaba PAI выявил ранее неизвестные уязвимости). Ключевые выводы: LLM-as-a-Judge сильно уязвим к атакам типа PAIR и combined attacks; defense-механизмы (re-tokenization, LLM-based detectors) усиливают защиту; robustness варьируется до 40% в зависимости от prompt template. Предложен метод оптимизации prompt-template; JudgeLM-13B показан как robust open-source judge.

## Почему релевантно
Прямой каталог attack vectors против LLM-judge (15 методов) + 7 defenses — must-have для собственного PostgreSQL-судьи. Если planируется LLM-as-judge для оценки уязвимости SQL, RobustJudge даёт готовый attack-suite (наша устойчивость должна меряться против PAIR, combined, autodan, uni, cheating и т.д.).

## README-превью (GitHub S3IC-Lab/RobustJudge)
Из реального README:
- Description: "a fully automated, scalable evaluation framework that systematically tests the robustness of 'LLM-as-a-Judge' systems against a broad set of adversarial attacks and defense strategies"
- Features: diverse attack types (heuristic & optimization-based), defenses, prompt-template / model choice studies, metrics SDR/iSDR/ASR
- Supported attacks: **autodan** (optimization-based), **uni**, **combined**, **naive**, **cheating**
- Supported tasks: translation (flores200), code translation, mathematics, knowledge assessment, text summarization
- Supported models: meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo, OpenAI (через OPENAI_BASE_URL/OPENAI_API_KEY), Together (TOGETHER_API_KEY)
- License: GPL-3.0
- Citation pointer: arxiv.org/abs/2506.09443

## Цитаты (verbatim)
- "we introduce RobustJudge, a fully automated and scalable framework designed to systematically evaluate the robustness of LLM-as-a-Judge systems"
- "RobustJudge investigates the effectiveness of 15 attack methods and 7 defense strategies across 12 models"
- "LLM-as-a-Judge systems are highly vulnerable to attacks such as PAIR and combined attacks"

## Верификация
- WebFetch arXiv abstract → подтверждены framework name, 15 attacks, 12 models, авторы
- WebFetch github.com/S3IC-Lab/RobustJudge README — реальный код, attack list соответствует
- Independent index: emergentmind.com/topics/llm-as-a-judge-evaluation, ui.adsabs.harvard.edu

## Источник
- WebFetch'нуто: 2026-05-18, URLs https://arxiv.org/abs/2506.09443, https://github.com/S3IC-Lab/RobustJudge
