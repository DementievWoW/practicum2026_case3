# ADVETA: Adversarial Table Perturbation Benchmark for Text-to-SQL

- **Status:** verified
- **Тип:** benchmark
- **Канонический URL:** https://arxiv.org/abs/2212.09994 (ACL 2022: https://aclanthology.org/2022.acl-long.142/)
- **Год / venue / CVE-ID:** 2022 — ACL 2022 (Oral). Код/данные: https://github.com/microsoft/ContextualSP

## Что это
Первый robustness-бенчмарк для Text-to-SQL, базирующийся на парадигме Adversarial Table Perturbation (ATP): возмущения вносятся не в NL-вопрос, а в саму таблицу (имена колонок, типы, состав схемы) в «натуральном и реалистичном» виде. Авторы: Xinyu Pi, Bing Wang, Yan Gao, Jiaqi Guo, Zhoujun Li, Jian-Guang Lou (Microsoft Research / соавторы). Все протестированные SOTA-модели существенно деградируют на ADVETA; даже наиболее устойчивая модель теряет ~14.0% качества в среднем и до 50.7% на самой жёсткой перетурбации.

## Почему релевантно
Релевантен задаче надёжности LLM-судьи и Text-to-SQL пайплайна на реальных PostgreSQL-схемах: позволяет проверять, что валидаторы и судья не «ломаются» при безобидно выглядящих изменениях в DDL (переименование колонок, синонимы, лишние таблицы) — типичный источник ошибок и потенциальных уязвимостей.

## README-превью (для GitHub) или ключевые поля CVE (для CVE)
Из аннотации: «we curate ADVETA, the first robustness evaluation benchmark featuring natural and realistic ATPs». Ключевые числа: 14.0% общее падение для лучшей модели; 50.7% на наиболее тяжёлой перетурбации. Код и данные релизованы в репозитории Microsoft `ContextualSP`.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2212.09994
- Цитаты: «the first robustness evaluation benchmark featuring natural and realistic ATPs»; «even the most robust model suffers from a 14.0% performance drop overall and a 50.7% performance drop on the most challenging perturbation».
