# Dataset — пары «NL → SQL» на схеме заказчика

Датасет для двух задач:
- **Execution Accuracy** генератора (NL → SQL, сравнение с эталоном);
- **Recall судьи** (уязвимый SQL → должен сработать класс).

Все SQL — на **реальных таблицах** `data_model.sql` (`credit_contract`, `acc_number`, `dict_product`, `ic_application`, `count_turnover`, ...).

## Состав

| Категория | sql_good | sql_bad | Зачем |
|---|---|---|---|
| **safe** | ✅ | — | эталон EX, few-shot генератора |
| **уязвимые** (9 классов) | ✅ (исправленная) | ✅ (с уязвимостью) | Recall судьи + демо «было→стало» |
| **медленные** (`SLOW_QUERY`, `NO_PAGINATION`) | ✅ | ✅ | тест EXPLAIN-проверок |

**Принцип «оба варианта»:** у каждого уязвимого примера ДВЕ версии SQL —
`sql_bad` (как НЕ надо) и `sql_good` (как надо, тот же интент). На `sql_bad`
судья обязан поднять класс, на `sql_good` — тишина.

## Файлы

```
dataset/
├── seed_examples.py    # SEED — рукописные примеры (ИСТОЧНИК, версионируется)
├── build_dataset.py    # SEED → back-translation → data/dataset_v1.jsonl
└── README.md           # этот файл

src/case3/dataset/models.py   # SeedExample, DatasetRecord
data/dataset_v1.jsonl         # СГЕНЕРИРОВАННЫЙ итог (gitignore)
```

## Как дополнять (роль «Данные»)

1. Открой `seed_examples.py`, добавь `SeedExample(...)` в список `SEED`.
2. Для **safe** — только `sql_good`. Для **уязвимого** — `sql_bad` + `sql_good`.
3. Используй **реальные таблицы и колонки** (сверяйся со `schema_catalog.json`).
4. Проверь метки: `python dataset/seed_examples.py` (валидация vuln_class/difficulty).
5. Пересобери: `python dataset/build_dataset.py`.

**Цель — 300 SQL** (сейчас 14 как образец). Баланс по ADR-0006:
~200 safe + ~100 уязвимых, по всем 9 классам.

## Формат записи (dataset_v1.jsonl)

```json
{
  "seed_id": "ds-dml-001",
  "nl": "закрыть кредитный договор с конкретным id",
  "sql": "UPDATE credit_contract SET status = 0",
  "vuln_class": "DML_NO_WHERE",
  "is_vulnerable": true,
  "difficulty": "easy",
  "tables": ["credit_contract"],
  "split": "train"
}
```

## Что пока mock (заменить в проде)

- **Back-translation** (`mock_back_translate`) — сейчас берёт `intent` и делает
  2 стиля. В проде — LLM-вызов (Qwen / GPT-4o-mini): «опиши SQL → дай 2 NL».
- **Валидация SQL** — пока только метки. В проде: `pglast.parse_sql` +
  исполнение safe-SELECT в sandbox-Postgres (ADR-0007 quality-gate).

## Открытый вопрос к заказчику

В схеме **нет очевидных PII-колонок** (password/passport). Для класса
`DIRECT_SENSITIVE` чувствительными считаем финансовые суммы
(`credit_amount`, обороты). **Список «sensitive» колонок нужно уточнить
у заказчика** (см. вопросы кураторам).
