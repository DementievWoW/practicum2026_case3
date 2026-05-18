# SQLQueryShield (salmane11/SQLQueryShield)

- **Status:** verified
- **Тип:** tool (модель) + связанный dataset
- **Канонический URL:** https://huggingface.co/salmane11/SQLQueryShield (датасет: https://huggingface.co/datasets/salmane11/SQLShield)
- **Год / venue / CVE-ID:** опубликовано на Hugging Face; сопутствующая методология описана в работе «SQL Injection Detection Using Fine-Tuned CodeBERT» (ETASR)

## Что это
Файнтюненная модель на базе `microsoft/codebert-base`, классифицирующая SQL-запросы на два класса: `MALICIOUS` (потенциально уязвимый / SQLi-подобный) и `SAFE`. Размер ~0.1B параметров, max_length=128 токенов. Обучена на датасете SQLShield (vulnerable и безопасные NLQ + сгенерированные ими SQL). Предназначена как post-generation фильтр и анализатор паттернов SQL-инъекций.

## Почему релевантно
Готовый baseline для LLM-судьи: post-filter, который можно вызывать после Text-to-SQL генерации и сравнивать с собственным решением. Даёт референсные ярлыки и пример пайплайна классификации в `transformers.pipeline("text-classification", ...)`.

## README-превью (для GitHub) или ключевые поля CVE (для CVE)
Из карточки модели (Hugging Face):
- Base: `microsoft/codebert-base`; fine-tuned on `salmane11/SQLShield`.
- Labels: `MALICIOUS` vs `SAFE`.
- Пример: `SELECT campus FROM campuses WHERE location = '' UNION SELECT database() --` → `MALICIOUS` (score≈0.9995).
- Пример: `SELECT package_option FROM tv_channel WHERE series_name = 'Sky Radio'` → `SAFE` (score≈0.9995).

## Источник
- WebFetch'нуто: 2026-05-18, URL https://huggingface.co/salmane11/SQLQueryShield
- Цитаты: «fine-tuned on SQLShield, a dataset dedicated to text-to-SQL vulnerability detection»; «Max Length: 128 tokens»; «Model Size: 0.1B parameters».
