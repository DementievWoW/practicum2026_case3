# RetrySQL: text-to-SQL training with retry data for self-correcting query generation

- **Status:** verified
- **Тип:** paper
- **Канонический URL:** https://arxiv.org/abs/2507.02529 (также AAAI Proceedings: https://ojs.aaai.org/index.php/AAAI/article/view/40556)
- **Год / venue:** AAAI 2026 (camera-ready, ноябрь 2025); arXiv v2 — 2025-07.

## Что это
Авторы (Alicja Rączkowska, Riccardo Belluzzo, Piotr Zieliński, Joanna Baran, Paweł Olszewski) предлагают новый формат обучающих данных — «retry data»: для каждой эталонной SQL цепочка reasoning-шагов искусственно портится, затем добавляется корректирующий шаг, разделитель — специальный токен. На continuous pre-training открытой code-модели это даёт прирост execution accuracy. По данным фетча: «up to 4 percentage point improvement in overall execution accuracy» и «up to 4 percentage point in challenging execution accuracy» (в web-сниппете встречается также «up to 4 and 9 pp» — расхождение источников; в самом arXiv abstract фигурирует «up to 4 pp»). Подчёркивается, что full-parameter pretraining обязателен — LoRA SFT не работает.

## Почему релевантно
Это ровно про то, как «вшить» само-исправление прямо в авторегрессионную генерацию SQL. Для GreenData это даёт альтернативу внешнему judge: модель сама в процессе генерации делает retry-шаги по клозам PostgreSQL-запроса.

## README-превью (GitHub-репо)
Ссылки на репозиторий в abstract не приведены; не применимо.

## Источник
- WebFetch'нуто: 2026-05-18, URL https://arxiv.org/abs/2507.02529
- Релевантные цитаты: «retry data containing both incorrect and corrected steps, divided with a special token»; «self-correction can be learned in the text-to-SQL task»; «full-parameter pre-training is necessary — supervised fine-tuning with LoRA proves ineffective».
