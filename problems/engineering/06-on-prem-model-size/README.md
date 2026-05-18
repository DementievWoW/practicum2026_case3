# 06 — Целевая модель ≤ 30B параметров

## Что

`case_3.txt` явно говорит:
> Целевая архитектура рассчитана на модели до 30 миллиардов параметров (например, Qwen-Coder 32B или специализированные code-модели), поскольку заказчик разворачивает систему в своём контуре с ограниченными ресурсами.

И там же:
> Контекстное окно моделей ограничено 100–256 тысячами токенов.

В то же время:
> Допускается использование публичных LLM API.

Это означает: **на хакатоне можно облако**, **но архитектура должна работать на on-prem модели ≤ 30B**, иначе на защите критерий «Обоснованность архитектурных решений» (10 баллов) проседает.

## Почему критично

10 баллов. Плюс — все «дополнительные баллы» за обоснованность подкосятся, если на вопрос жюри «а в контуре заказчика как развернётесь?» ответ «никак, нужен GPT-4o» — мы сразу теряем зрелость решения.

Из обзора (`research/05_peripheral.md` § 2):
- **Qwen2.5-Coder 32B** — лидер открытых code-моделей, HumanEval 88.4% (выше GPT-4 87.1%).
- **DeepSeek-Coder V2-Lite 16B** — быстрее, но качество ниже.
- На SQL — Qwen стабильно в топ-3 (Tinybird, Beekeeper benches).

Подходящие кандидаты — есть. Но архитектуру надо адаптировать.

## Силы, тянущие в разные стороны

| Куда тянет | Аргумент |
|---|---|
| **GPT-4o / Claude Sonnet** | Качество выше, простой API |
| **Qwen-Coder 32B (open)** | Соответствует требованию, заказчик развернёт |
| **Облачный inference** | Простой, быстрый, дешёвый на хакатоне |
| **Локальный vLLM** | Идеальная демонстрация on-prem |
| **Один и тот же модель на все узлы** | Простота |
| **Разные модели на узлы** | Экономия (reflector — 7B, generator — 32B) |
| **Жёсткая привязка к Qwen** | Не закрыт API-агностик контракт |
| **OpenAI-compat абстракция** | Переключение моделей за конфиг |

## Наше решение (ADR-0008)

### Базовая модель — Qwen2.5-Coder-32B-Instruct

| Узел | Модель | Почему |
|---|---|---|
| Generator | Qwen2.5-Coder-32B | Лучшее SQL качество в категории ≤ 30B |
| Auditor (judge) | Qwen2.5-Coder-32B | Тот же, JSON-mode, structured |
| Reflector | Qwen2.5-7B-Instruct | Задача проще, ×4-5 дешевле |

Qwen «технически» 32B, чуть выше формального порога 30B. На защите проговариваем это явно: модель **в категории «маленьких» по индустрии**, заказчик может запустить на 1×A100 80GB или 2×A100 40GB.

### Контракт — OpenAI-совместимый

```python
@dataclass
class LLMConfig:
    model: str
    base_url: str
    api_key: str
    temperature: float = 0.2
    max_tokens: int = 2048
    response_format: dict | None = None
    timeout_s: float = 30

class LLMClient:
    def __init__(self, cfg: LLMConfig): ...
    def chat(self, messages: list[dict]) -> ChatResponse: ...
```

Узлы LangGraph получают `LLMClient` через DI. В тестах подсовываем mock или маленькую модель. На дев — DeepInfra. На demo — может быть локальный vLLM.

### Провайдеры (на хакатон)

| Провайдер | $/1M токенов | Why |
|---|---|---|
| **DeepInfra** (primary) | ~$0.66 / ~$0.66 | Самый дешёвый, JSON-mode |
| **OpenRouter** (secondary) | $0.66 / $1.00 | Шире палитра для A/B |
| **YandexGPT** (integration test) | — | Российский, важно для GreenData |

### Бюджет per-run

`total_token_budget_per_run = 80_000` (in+out, ADR-0008 §4). Если превышен — `budget_exhausted=true`, finalize с лучшим имеющимся.

### Fallback на облачный gpt-4o-mini

Если на eval-set EX < 70% с Qwen-Coder 32B — включаем `gpt-4o-mini` как primary. На защите позиционируем как «архитектура агностична к модели; целевой контур — Qwen, на хакатоне разрешено облако».

### Локальный vLLM (если будет время)

Раздел «после MVP». Поднимаем vLLM с Qwen2.5-Coder-32B на 2×A100 (или 4-bit quantized на 1×A100). Демо переключается на локальный endpoint. **Это самая сильная стороной защиты**, если успеем.

## Trade-off

**Жертвуем:** не дотягиваем до качества GPT-4o (~5-10 п.п. EX в типичной картине).
**Получаем:** релевантность кейсу. На вопрос «а как это работает в контуре?» — «вот, разворачиваем Qwen, всё работает».

## Что измеряем

| Метрика | Цель | Источник |
|---|---|---|
| **EX на Qwen-Coder 32B** | ≥ 70% | eval-set ADR-0007 |
| **Recall судьи на Qwen** | ≥ 0.80 | то же |
| **Cost per run** (DeepInfra Qwen) | < $0.05 | provider API |
| **Cost A/B vs GPT-4o-mini** | дельта EX vs дельта стоимости | A/B-эксперимент |
| **Доступность модели через 3 провайдера** | 3/3 работают | smoke test |
| **YandexGPT integration test** | проходит | один прогон через YGPT |

## Связи

- **ADR-0008** — LLM choice and inference provider (главный design doc).
- **ADR-0002** — generator/auditor/reflector узлы.
- **ADR-0007** — eval-методология для измерения.
- **research/05_peripheral.md** § 2 — сравнение моделей.
- **research/materials/01-generators-multiagent/bappa/** — паттерн multi-agent discussion на малых моделях.
- **research/materials/01-generators-multiagent/mag-sql/** — MAG-SQL на малых моделях.
- **research/materials/02-critics-self-correction/msc-sql/** — Multi-Sample Critiquing специально для small models.

## Что может пойти не так

1. **Qwen-Coder 32B провайдером сделан недоступным** в день защиты. Митигация: secondary через OpenRouter; fallback на gpt-4o-mini.
2. **Provider не поддерживает JSON-mode для Qwen** (DeepInfra умеет, OpenRouter — частично). Митигация: Pydantic-validator + retry × 2 даже на raw text output.
3. **Контекст 100K забивается** на retry-итерации с большой reflection-памятью. Митигация: token budget cap + truncation reflection до 5 последних lesson-ов (см. [02-reflection-memory-loop](../02-reflection-memory-loop/)).
4. **Качество на русском просаживается** — Qwen-Coder обучен в основном на английском, judge может «выпадать» в смесь языков. Митигация: явная инструкция в system-промпте «отвечай по-русски» + `temperature=0.1` для judge.
5. **Локальный vLLM не успеваем поднять** к защите. Митигация: оставляем как stretch goal, не блокер.
