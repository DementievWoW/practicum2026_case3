# SCoT2S: Self-correcting Text-to-SQL parsing by leveraging LLMs

- **Status:** verified (через WebSearch; ScienceDirect-страница отдала HTTP 403, но публикация однозначно индексируется)
- **Тип:** paper (journal)
- **Канонический URL:** https://www.sciencedirect.com/science/article/pii/S0885230825000907
- **Год / venue:** 2025 (по DOI S0885230825000907 — Computer Speech & Language / журнал Elsevier; пользователь указал «2026», это **не подтверждено**, журнал — 2025)

## Что это
Фреймворк SCoT2S для self-correcting text-to-SQL парсинга. Трёхстадийный пайплайн: (1) начальная генерация SQL, (2) комплексная детекция ошибок, (3) targeted-коррекция через LLM. Авторы анализируют, что >70% ошибок в существующих моделях приходится на schema linking и join operations. Сообщается о +2.8% EM и +4.0% EX на Spider относительно тогдашних SOTA.

## Почему релевантно
Прямой пример многоступенчатой self-correction архитектуры с фокусом на joins и schema linking — частые источники ошибок в энтерпрайз-сценариях GreenData. Цифры — ориентир для прироста от слоя коррекции.

## README-превью (для GitHub)
—

## Источник
- WebFetch'нуто: 2026-05-18, https://www.sciencedirect.com/science/article/pii/S0885230825000907 — HTTP 403
- WebSearch ("SCoT2S self-correction text-to-SQL") — публикация подтверждена, описание извлечено из агрегированных результатов
- Цитаты (из WebSearch agg.):
  - "SCoT2S … addresses text-to-SQL parsing issues through a three-stage approach: initial SQL generation, comprehensive error detection, and targeted correction using large language models"
  - "schema linking and join operations account for over 70% of parsing errors"
  - "2.8% increase in EM scores and a 4.0% increase in EX scores compared to current state-of-the-art methods"

## Коррекция
Пользователь указал «SCoT2S 2026»; по DOI это 2025 publication в Elsevier-журнале (Computer Speech & Language / Speech Communication, серия S08852308).
