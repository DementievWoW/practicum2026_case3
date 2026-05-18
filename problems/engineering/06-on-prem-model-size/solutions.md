# Варианты решения: LLM ≤ 30B параметров

## Альтернативные подходы

| # | Подход | Плюсы | Минусы | Решение |
|---|---|---|---|---|
| A | GPT-4o / Claude Sonnet | Лучшее качество | Не закрывает требование «≤ 30B в контуре заказчика» | ❌ как primary; fallback ok |
| B | **Qwen2.5-Coder 32B через DeepInfra/OpenRouter** | Лидер open-source ≤ 30B; дёшево | Чуть выше формального порога 30B | ✅ выбрали |
| C | DeepSeek-Coder V2-Lite 16B | Дешевле, быстрее | Качество SQL ниже Qwen 32B | для cost-sensitive прогонов |
| D | StarCoder2 | Open-source | Отстаёт по SQL | как baseline для fine-tune |
| E | Локальный vLLM с Qwen 32B | Полный on-prem; идеал для защиты | GPU нужно (2×A100 или 4-bit квант) | stretch goal |
| F | Fine-tune Qwen-Coder на нашем датасете 300 пар | Доменно-точный | 300 пар недостаточно для fine-tune; вне MVP | для v2 |
| G | YandexGPT (российский провайдер) | Релевантно заказчику | OpenAI-compat частичная, ограниченное SQL качество | integration-test |

## Распределение моделей по узлам

| Узел | Модель | Почему |
|---|---|---|
| Generator | Qwen2.5-Coder-32B | Лучшее SQL качество в категории ≤ 30B |
| Auditor (judge) | Qwen2.5-Coder-32B | Тот же, JSON-mode, structured |
| Reflector | Qwen2.5-7B-Instruct | Задача проще, ×4-5 дешевле |

## Что выбрали и почему

**B как primary, C/E/G как опции, A как emergency fallback.**

Аргументы:
- **Qwen2.5-Coder 32B Apache-2.0** — заказчик может развернуть в контуре без юридических вопросов.
- Технически чуть выше 30B, но в индустрии считается «в категории small» (Hugging Face leaderboards, заявления Qwen). На защите проговариваем явно.
- **OpenAI-compat контракт** — переключение между провайдерами и моделями одной строкой.
- **DeepInfra** primary за лучшую цену ($0.66/$0.66 за 1M tokens).
- **Локальный vLLM (E)** — stretch goal; если успеваем — это **самая сильная сторона защиты**.

## Реализация (ADR-0008)

### Контракт LLM-клиента (OpenAI-совместимый)

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

Узлы LangGraph получают `LLMClient` через DI. В тестах подсовываем mock или маленькую модель.

### Провайдеры

| Провайдер | Цена за 1M токенов | Назначение |
|---|---|---|
| **DeepInfra** (primary) | ~$0.66 / ~$0.66 | Самый дешёвый, JSON-mode |
| **OpenRouter** (secondary) | $0.66 / $1.00 | A/B и шире палитра |
| **YandexGPT** (integration test) | — | Российский, важно для GreenData |
| **gpt-4o-mini** (emergency fallback) | $0.15 / $0.60 | Если Qwen-Coder не дотянет до 70% EX |

### Бюджет per-run

`total_token_budget_per_run = 80_000` (in+out, ADR-0008 §4). Если превышен — `budget_exhausted=true`, finalize с лучшим имеющимся.

### Хранение ключей

`.env` локально, gitignore'нуто, `.env.example` в репо. На дев-сервере / CI — secrets manager.

### Локальный vLLM (если успеваем)

vLLM с Qwen2.5-Coder-32B на 2×A100 (или 4-bit quantized на 1×A100). Демо переключается на локальный endpoint. **Главный экспонат защиты, если успеем.**

## Что измеряем

| Метрика | Цель |
|---|---|
| **EX на Qwen-Coder 32B** | ≥ 70% |
| Recall судьи на Qwen | ≥ 0.80 |
| Cost per run (DeepInfra Qwen) | < $0.05 |
| Cost A/B vs GPT-4o-mini | дельта EX vs дельта стоимости |
| Доступность модели через 3 провайдера | 3/3 работают |
| YandexGPT integration test | проходит smoke |

## Что может пойти не так

| Проблема | Митигация |
|---|---|
| Qwen 32B недоступен у провайдера в день защиты | Secondary через OpenRouter; fallback на gpt-4o-mini |
| Provider не поддерживает JSON-mode для Qwen (OpenRouter частично) | Pydantic-validator + retry × 2 на raw text |
| Контекст 100K забивается при больших reflection-памятях | Token budget cap + truncation до 5 lessons |
| Качество на русском просаживается у Qwen-Coder | `temperature=0.1` для judge + системный промпт «отвечай по-русски» |
| Локальный vLLM не успеваем поднять | Stretch goal, не блокер; cloud работает на демо |
| EX < 70% на Qwen — fallback на gpt-4o-mini ломает «on-prem» аргумент защиты | Документируем «архитектура агностична; цель — Qwen, для измерений использовали и gpt-4o-mini» |

## Связи с ADR

- **ADR-0008** — LLM choice and inference provider (главный design doc).
- **ADR-0002** — generator/auditor/reflector узлы.
- **ADR-0007** — eval-методология для измерения.
