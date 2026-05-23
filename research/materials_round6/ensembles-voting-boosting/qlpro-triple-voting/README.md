# QLPro: Automated Code Vulnerability Discovery via LLM and Static Code Analysis Integration

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2506.23644
- **Год / venue:** 2025, arXiv:2506.23644 (cs.SE)
- **Авторы:** Junze Hu, Xiangyu Jin, Yizhe Zeng, …

## Что это
Фреймворк автодетекции уязвимостей: **LLM поверх статанализа** (CodeQL-правила).
Ключевой приём — **triple-voting**: каждый API оценивается LLM в 3 разных
контекстных группах независимо, итог — majority vote (снижает context
interference). Результат: 41/62 уязвимостей против 24/62 у голого CodeQL, +6 0-day.

## Почему релевантно нашему кейсу (ADR-0012)
Канонический прецедент нашей схемы судьи: **голосующие LLM-судьи НАД
детерминированным слоем** (= наш Phase 1 на pglast). Triple-voting одной моделью
в разных контекстах — дешёвый способ де-коррелировать голоса **без** второго
семейства (созвучно [Self-MoA](../self-moa/)). Прямо мотивирует Stage 0 → Stage 1
каскад из ADR-0012.

## Цитаты (verbatim из arXiv abstract)
- "a vulnerability detection framework that systematically integrates LLMs and static analysis tools to enable comprehensive vulnerability detection"
- "CodeQL, a state-of-the-art static analysis tool, detected only 24 of these vulnerabilities while QLPro detected 41."

## Источник
- WebFetch'нуто: 2026-05-23, https://arxiv.org/abs/2506.23644 (успешно)
