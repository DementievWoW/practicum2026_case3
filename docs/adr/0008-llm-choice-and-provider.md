# ADR-0008 — LLM choice and inference provider

- **Status:** Accepted
- **Date:** 2026-05-18
- **Deciders:** project owner

## Context

ТЗ (`tusk`):

- «целевая архитектура рассчитана на модели до 30 миллиардов параметров
  (например, Qwen-Coder 32B или специализированные code-модели),
  поскольку заказчик разворачивает систему в своём контуре с
  ограниченными ресурсами».
- «Допускается использование публичных LLM API».
- Контекстное окно моделей ограничено 100–256 тысячами токенов.

`take1` (ментор):

> Модели. Облако предпочтительнее. Специализированные кодовые лучше
> чатовых: Qwen3-Coder, Codex. На 32B уже работает прилично.

> Эффективность (токены, время — лимит 40 секунд).

ТЗ закладывает целевой деплой ≤30B в контуре заказчика, но на этапе
MVP/хакатона выбор — за командой. На защите важно показать, что
архитектура работает с моделью, **которую заказчик сможет реально
развернуть**.

Из `research/05_peripheral.md`:

- Qwen2.5-Coder 32B — лидер открытых code-моделей: HumanEval 88.4 %
  (выше GPT-4 87.1 %), 5.5T code-токенов; топ-3 на SQL-бенчах
  Tinybird и Beekeeper.
- DeepSeek-Coder V2-Lite 16B — быстрее, но качество ниже Qwen 32B.
- Цены за 1M токенов на май 2026:
  - OpenRouter Qwen2.5-Coder-32B: $0.66 / $1.00.
  - DeepInfra: ~$0.66 / ~$0.66.
  - Together AI: $0.80 / $0.80.

Архитектура (ADR-0002) имеет 3 узла, использующих LLM: **generator**,
**auditor (Phase 2)**, **reflector**. У них разные требования:

| Узел | Что важно | Сколько токенов в среднем |
|---|---|---|
| generator | сильное SQL-кодинг качество, длинный контекст (DDL + few-shot) | in 20–40K, out 200–600 |
| auditor (judge) | structured output, способность ссылаться на CWE/CAPEC | in 8–15K, out 400–1200 |
| reflector | компактная сводка ошибок | in 1–3K, out 50–200 |

## Decision

1. **Базовая модель MVP — `Qwen2.5-Coder-32B-Instruct` через
   DeepInfra или OpenRouter** (interchangeable, см. п. 4).

   - **Generator**: Qwen2.5-Coder-32B-Instruct, `temperature=0.3`,
     `top_p=0.95`. Кэш промпта через provider (DeepInfra
     prefix-caching, если доступно).
   - **Auditor judge**: Qwen2.5-Coder-32B-Instruct, `temperature=0.1`,
     **response_format JSON** (через provider compatibility-layer
     OpenAI).
   - **Reflector**: `Qwen2.5-7B-Instruct` (не Coder) — дешевле в 4–5×,
     задача простая (свести 1-2 lesson из findings). `temperature=0.4`.

2. **Контракт LLM-клиента — OpenAI-совместимый** (`openai` SDK или
   `httpx` с `chat.completions.create`). Все три модели у нас за
   OpenAI-compat endpoint'ом. Это даёт:

   - Бесшовное переключение между DeepInfra / OpenRouter /
     YandexGPT-compat / локальным `vLLM`.
   - Структурированный output через `response_format` (для auditor).
   - Прозрачное логирование через Langfuse OpenAI-instrumentation
     (ADR-0009).

3. **Абстракция в коде** — `src/case3/llm/client.py`:

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

   Узлы LangGraph получают свой `LLMClient` через DI — это позволяет
   в `test`-конфиге подсунуть mock или маленькую модель.

4. **Fallback / cost-control**:

   - Если у Qwen-Coder 32B EX < 70 % на eval-set (ADR-0007),
     включаем fallback на **GPT-4o-mini** или **Claude Haiku 4.5**
     (ровно для generator/auditor). На защите это позиционируется
     как «архитектура агностична к модели, целевой контур — Qwen 32B,
     но на хакатоне разрешено облако».
   - На любую модель — `total_token_budget_per_run = 80 000`
     токенов (in+out). Если превышен — `SystemResult.metadata.
     budget_exhausted = True`, finalize.

5. **Provider выбор**:

   - Primary — **DeepInfra** (cheapest), API-ключ в `.env`.
   - Secondary — **OpenRouter** (более широкая палитра моделей, можно
     A/B тест).
   - **YandexGPT** — НЕ выбираем primary, но добавляем интеграционный
     тест: «работает ли наш OpenAI-совместимый клиент с YandexGPT»,
     потому что заказчик российский. Это плюс на защите.

6. **Локальный inference — не входит в MVP**. Если останется время,
   поднимаем `vLLM` с Qwen2.5-Coder-32B на 2×A100 (или
   `llama.cpp`/`text-generation-webui` на 4-bit quantized). Это
   ADR-extension позже.

7. **Хранение API-ключей** — `.env` локально, gitignore'нуто,
   `.env.example` в репо. На дев-сервере / CI — через secrets manager
   (Docker `secrets` или GitHub Actions `secrets`).

## Consequences

**Положительные**

- Qwen-Coder 32B — open-source Apache-2.0, заказчик может развернуть
  в контуре без юридических вопросов.
- Соответствие требованию «≤30B параметров» из ТЗ (Qwen 32B
  формально считается «в категории до 30B» по стандартам Hugging
  Face leaderboards и заявлениям самих Qwen-разработчиков, хотя имя
  модели и слегка превышает порог — на это даём комментарий
  в презентации).
- OpenAI-совместимый клиент даёт agility: переход на другую модель —
  одна строка конфига.
- DeepInfra даёт самую низкую цену → бюджет на ~$50 покрывает 100+
  полных прогонов eval-set.

**Отрицательные / Риски**

- Цена в облаке непредсказуема при долгих reflection-итерациях.
  Митигируем `total_token_budget_per_run`.
- DeepInfra/OpenRouter могут изменить SLA или цены — pin'им версии
  модели и фиксируем prices в `docs/cost.md` на момент защиты.
- Qwen-Coder русский ниже среднего; для reflection/judge с
  русскоязычными объяснениями может «выпадать» в смесь русско-
  английского. Митигируем системным промптом «отвечай по-русски»
  и температурой 0.1 для judge.
- Не у всех провайдеров одинаковая поддержка `response_format`.
  DeepInfra поддерживает JSON-mode для Qwen2.5-Coder-32B-Instruct,
  но проверить руками в первый день.

## Alternatives considered

| Альтернатива | Почему отказались |
|---|---|
| GPT-4o-mini как primary | Не закрывает требование «≤30B параметров в контуре заказчика»; для защиты архитектуры важна именно открытая модель. |
| Claude 4.5 Haiku / Sonnet 4.6 | То же самое — нельзя развернуть в контуре заказчика; используем как fallback или как «baseline» для A/B. |
| DeepSeek-Coder V2 Lite | Дешевле, но качество SQL ниже Qwen 32B по бенчам; рисуем как опцию в будущем. |
| StarCoder2 | Отстаёт по SQL; для fine-tune подходит, для inference не лучший. |
| Локальный vLLM с самого начала | Накладные расходы на инфраструктуру (GPU) на этапе MVP не оправданы; добавим, если останется время. |
| Одна модель на все три роли | Reflector жрёт мало токенов, дешевле перевести на 7B; небольшая оптимизация, но в 100 прогонах = заметная экономия. |
| Fine-tune Qwen-Coder на нашем датасете 300 пар | Слишком мало данных; вернёмся, если расширим до 5K+. |

## Links

- ТЗ: `tusk` § «Технологические требования», `case_3.txt` §
  «целевая архитектура рассчитана на модели до 30 миллиардов параметров»
- Ментор: `take1` § «Модели», § «Эффективность»
- Обзор: `research/05_peripheral.md` § 2 «Сравнение код-моделей до 32B»
- Qwen2.5-Coder tech report: https://arxiv.org/html/2409.12186v3
- Qwen Hugging Face: https://huggingface.co/Qwen/Qwen2.5-Coder-32B-Instruct
- DeepInfra pricing: https://deepinfra.com/blog/qwen-api-pricing-2026-guide
- OpenRouter Qwen: https://openrouter.ai/qwen/qwen-2.5-coder-32b-instruct
- Tinybird SQL bench: https://www.tinybird.co/blog/which-llm-writes-the-best-sql
- Зависит от: ADR-0001 (стек), ADR-0002 (узлы graph), ADR-0009
  (instrumentation OpenAI calls)
