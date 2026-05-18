# ErrorLLM: Modeling SQL Errors for Text-to-SQL Refinement

- **Status:** verified
- **Тип:** paper (arXiv preprint)
- **Канонический URL:** https://arxiv.org/abs/2603.03742
- **Год / venue:** 2026 (submission March 4, 2026), arXiv cs.CL

## Что это
ErrorLLM моделирует ошибки text-to-SQL генерации специальными «error tokens» в семантическом пространстве LLM. Пайплайн: представляет вопрос и схему как структурные фичи, через static detection ловит execution failures и surface mismatches, расширяет пространство LLM выделенными error-токенами по категориям имплицитных ошибок, и через специальную тренировку учит модель предсказывать эти токены — после чего делает error-guided refinement SQL-структуры. Авторы: Zijin Hong, Hao Chen, Zheng Yuan, Qinggang Zhang, Luyao Zhuang, Qing Liao, Feiran Huang, Yangqiu Song, Xiao Huang.

## Почему релевантно
Прямо ложится в наш блок self-correction / валидаторов: статья выделяет проблему, что «self-debugging становится всё менее эффективным, потому что современные LLM редко выдают явные execution errors, на которые можно повесить debug-сигнал». Идея error-tokens — кандидат к рассмотрению в архитектуре GreenData как способ структурировать сигналы от детерминированных валидаторов.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2603.03742
- Цитаты:
  - "existing paradigms face two major limitations: (i) self-debugging becomes increasingly ineffective as modern LLMs rarely produce explicit execution errors that can trigger debugging signals"
  - "ErrorLLM … explicitly models text-to-SQL errors within dedicated error tokens for text-to-SQL refinement"
