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
├── seed_examples.py     # SEED — рукописные примеры-якоря (ИСТОЧНИК, версионируется)
├── build_dataset.py     # SEED → back-translation → JSONL (мелкий набор-образец)
├── generate_dataset.py  # СИНТЕЗ 500 записей по реальной схеме (основной билдер)
├── sensitive_overlay.sql# PII-overlay sim_* для класса DIRECT_SENSITIVE
└── README.md            # этот файл

src/case3/dataset/models.py   # SeedExample, DatasetRecord, VULN_CLASSES
data/schema_catalog.json      # схема заказчика (60 таблиц) — вход генератора
data/dataset_v1.jsonl         # СГЕНЕРИРОВАННЫЙ итог, 500 записей (gitignore)
```

## Генерация 500 записей

```bash
python dataset/generate_dataset.py            # 500 → data/dataset_v1.jsonl
python dataset/generate_dataset.py --n 1000   # другой объём
```

`generate_dataset.py` читает `schema_catalog.json`, классифицирует колонки
каждой таблицы (id / FK / сумма / дата / текст / статус) и собирает валидный
SQL по шаблонам на **реальных таблицах и колонках**. Рукописные seed-примеры
подмешиваются как приоритетные якоря, дальше пул добивается шаблонами.
Генерация **детерминированна** (`random.Random(42)` только для split).

Текущий состав: **500** записей = **300 safe + 200 уязвимых** (по ~18–22 на
каждый из 10 классов), 50 задействованных таблиц, 0 дублей SQL, train/eval ≈ 405/95.
Все запросы парсятся `sqlglot` (postgres-диалект); классические инъекции
синтаксически валидны — уязвимость семантическая.

## Как дополнять (роль «Данные»)

1. Открой `seed_examples.py`, добавь `SeedExample(...)` в список `SEED`.
2. Для **safe** — только `sql_good`. Для **уязвимого** — `sql_bad` + `sql_good`.
3. Используй **реальные таблицы и колонки** (сверяйся со `schema_catalog.json`).
4. Проверь метки: `python dataset/seed_examples.py` (валидация vuln_class/difficulty).
5. Пересобери: `python dataset/build_dataset.py`.

**Текущий объём — 500 SQL** (`generate_dataset.py`). Баланс: 300 safe +
200 уязвимых по всем 10 классам. Чтобы добавить выверенные примеры —
правь `seed_examples.py` (они идут якорями впереди шаблонных).

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

- **NL-формулировки** — генерятся из `intent` по шаблонам (детерминированно,
  без LLM). В проде можно усилить LLM-парафразом (Qwen / GPT-4o-mini):
  «опиши SQL → дай 2 NL-вопроса аналитика».
- **Валидация SQL** — структурная (`sqlglot` парсит все 500). В проде ещё:
  исполнение safe-SELECT в sandbox-Postgres + `EXPLAIN` (ADR-0007 quality-gate).

## Sensitive-колонки

В основной мета-схеме PII всё же **есть**: `sys_employee` (`email`, `phone`,
`birthday`, `first_name`/`sur_name`), `sys_company` (`inn`, `contact_phone`,
`attr_email`). Плюс синтетический overlay `sim_*` (`sensitive_overlay.sql`):
паспорт, СНИЛС, номер карты, CVV, хеш пароля, API-токен. На них и построен
класс `DIRECT_SENSITIVE` (`SENSITIVE_COLS` в `generate_dataset.py`).
Финальный список «sensitive» для прода — **уточнить у заказчика** (вопрос
кураторам); правится в одном месте — словаре `SENSITIVE_COLS`.
